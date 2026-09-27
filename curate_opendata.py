#!/usr/bin/env python3
"""Discovery from the iNaturalist Open Data metadata (stdlib only).

Streams the four monthly tables from the public bucket (taxa, observations,
photos, observers; tab-separated .csv.gz, ~33 GB compressed) and filters on the
fly, so nothing but the matches needs to fit on disk:

  taxa          -> every descendant of each requested taxon_id (subspecies etc.;
                   hybrids and "x" names dropped)
  observations  -> quality_grade=research AND taxon in that set
  photos        -> licence CC0 / CC-BY (CC-BY-SA only with --by-sa); NC/ND never
  observers     -> name + login for attribution

Writes a manifest with the same columns as the published manifest_*_public.csv
files (so fetch_inat.py and everything after it work unchanged), plus
snapshot_date, observation_uuid and target_taxon_id. The snapshot is up to ~31
days old: run verify_selection.py over the final selection before using it.

    python3 curate_opendata.py species.json manifest.csv [--want 60] [--per-obs 2]
        [--per-observer 5] [--by-sa] [--coords coords.tsv] [--cache-dir DIR]

species.json = {"<label>": <iNat taxon_id>, ...}. --source takes a directory of
.csv.gz files instead of the bucket (tests, or an unpacked monthly tarball).
Ordering replaces the API's vote order: each observation's first photo
(position 0) before any second photo, a size floor (--min-px, long side), then
photo_uuid (random, so reproducible but unbiased), with the per-observation and
per-observer caps applied in that order.
"""
import argparse, csv, email.utils, gzip, json, os, shutil, subprocess, sys, time, urllib.request

BASE = "https://inaturalist-open-data.s3.amazonaws.com/"
UA = "DeepSix-Fishial-Benchmark/0.1 (research curation; support@deepsixdive.com)"
# Open Data licence strings are unversioned; iNat photo licences are the 4.0 deeds.
LIC = {"CC0": ("cc0", "CC0", "https://creativecommons.org/publicdomain/zero/1.0/"),
       "CC-BY": ("cc-by", "CC-BY 4.0", "https://creativecommons.org/licenses/by/4.0/"),
       "CC-BY-SA": ("cc-by-sa", "CC-BY-SA 4.0", "https://creativecommons.org/licenses/by-sa/4.0/")}
COLUMNS = ["species", "photo_id", "url", "license", "author", "author_login", "observed_on",
           "source_page", "attribution", "sha256", "license_code", "license_url", "taxon_id",
           "retrieved_utc", "snapshot_date", "observation_uuid", "target_taxon_id"]
BYTES = {}  # table -> compressed bytes read


class _Tee:
    """File-like wrapper: counts bytes and optionally copies them to a cache file."""
    def __init__(self, src, name, copy=None):
        self.src, self.name, self.copy = src, name, copy
        BYTES[name] = 0

    def read(self, n=-1):
        b = self.src.read(n)
        BYTES[self.name] += len(b)
        if self.copy: self.copy.write(b)
        return b


def rows(name, source, cache_dir=None):
    """Return (column index, iterator of byte-field lists) for <name>.csv.gz; sets rows.date."""
    fn = name + ".csv.gz"
    local = os.path.join(source, fn) if not source.startswith("http") else None
    if cache_dir and not local and os.path.exists(os.path.join(cache_dir, fn)):
        local = os.path.join(cache_dir, fn)
    if local:
        f, copy, lm = open(local, "rb"), None, os.path.getmtime(local)
    else:
        f = urllib.request.urlopen(urllib.request.Request(source + fn, headers={"User-Agent": UA}), timeout=120)
        lm = email.utils.parsedate_to_datetime(f.headers["Last-Modified"]).timestamp()
        copy = open(os.path.join(cache_dir, fn + ".part"), "wb") if cache_dir else None
    rows.date = rows.date or time.strftime("%Y-%m-%d", time.gmtime(lm))  # snapshot = first table's date
    proc = None
    if local and shutil.which("gzip"):  # a separate gzip process parses ~2x faster (41 vs 21 MB/s)
        BYTES[name] = os.path.getsize(local); f.close()
        proc = subprocess.Popen(["gzip", "-dc", local], stdout=subprocess.PIPE, bufsize=1 << 20)
        g = proc.stdout
    else:
        g = gzip.GzipFile(fileobj=_Tee(f, name, copy))
    header = g.readline().rstrip(b"\n").decode().split("\t")

    def it():
        for line in g:
            yield line.rstrip(b"\n").split(b"\t")
        g.close()
        if proc and proc.wait(): raise RuntimeError(f"gzip -dc {local} failed")  # never a silent short read
        f.close()
        if copy:  # complete download only; the cached file keeps the bucket's date
            copy.close(); os.replace(copy.name, copy.name[:-5]); os.utime(copy.name[:-5], (lm, lm))
    return {c: i for i, c in enumerate(header)}, it()
rows.date = None


def descendants(targets, source, cache_dir):
    """taxon_id(bytes) -> (target id, taxon name) for each target and its non-hybrid descendants."""
    h, it = rows("taxa", source, cache_dir)
    want, out = {str(t).encode() for t in targets}, {}
    for r in it:
        tid, name = r[h["taxon_id"]], r[h["name"]].decode()
        if r[h["rank"]] == b"hybrid" or "×" in name: continue
        chain = r[h["ancestry"]].split(b"/") + [tid]
        hit = next((a for a in reversed(chain) if a in want), None)  # most specific target wins
        if hit: out[tid] = (int(hit), name)
    return out


def curate(species, source=BASE, cache_dir=None, want=0, per_obs=0, per_observer=0, by_sa=False,
           min_px=0, coords=None, max_acc=10000, min_anomaly=1.0, log=print):
    rows.date, label = None, {int(t): s for s, t in species.items()}
    tax = descendants(label, source, cache_dir)
    log(f"taxa: {len(tax)} ids under {len(label)} targets")
    h, it = rows("observations", source, cache_dir)
    ti, qi = h["taxon_id"], h["quality_grade"]
    obs, cw = {}, csv.writer(open(coords, "w", newline=""), delimiter="\t") if coords else None
    if cw: cw.writerow(["species", "latitude", "longitude", "positional_accuracy", "anomaly_score"])
    for r in it:
        if r[ti] not in tax or r[qi] != b"research": continue
        d = {c: r[i].decode() for c, i in h.items()}
        obs[r[h["observation_uuid"]]] = d
        acc, an = d["positional_accuracy"], d["anomaly_score"]
        # anomaly_score < 1.0 = geomodel says "not expected nearby"; blank = no score, kept
        if cw and d["latitude"] and (not acc or float(acc) <= max_acc) and (not an or float(an) >= min_anomaly):
            cw.writerow([label[tax[r[ti]][0]], d["latitude"], d["longitude"], acc, an])
    log(f"observations: {len(obs)} research-grade")
    ok = {"CC0", "CC-BY"} | ({"CC-BY-SA"} if by_sa else set())
    h, it = rows("photos", source, cache_dir)
    oi, li = h["observation_uuid"], h["license"]
    photos, seen = [], {}
    for r in it:
        if r[oi] not in obs: continue
        lic = r[li].decode(); seen[lic] = seen.get(lic, 0) + 1
        if lic in ok: photos.append({c: r[i].decode() for c, i in h.items()})
    log(f"photos: {seen} (kept {sorted(ok)})")
    need = {p["observer_id"] for p in photos}
    h, it = rows("observers", source, cache_dir)
    people = {r[h["observer_id"]].decode(): (r[h["login"]].decode(), r[h["name"]].decode())
              for r in it if r[h["observer_id"]].decode() in need}
    by = {}
    for p in photos:
        o = obs[p["observation_uuid"].encode()]
        by.setdefault(label[tax[o["taxon_id"].encode()][0]], []).append((p, o))
    out = []
    for sp in species:
        cand = [(p, o) for p, o in by.get(sp, [])
                if max(int(p["width"] or 0), int(p["height"] or 0)) >= min_px]
        cand.sort(key=lambda po: (int(po[0]["position"] or 0), po[0]["photo_uuid"]))
        n_obs, n_user, kept, ids = {}, {}, [], set()
        for p, o in cand:
            u = o["observer_id"]
            if p["photo_id"] in ids: continue  # one photo can sit on two observations
            ids.add(p["photo_id"])
            if per_obs and n_obs.get(p["observation_uuid"], 0) >= per_obs: continue
            if per_observer and n_user.get(u, 0) >= per_observer: continue
            n_obs[p["observation_uuid"]] = n_obs.get(p["observation_uuid"], 0) + 1
            n_user[u] = n_user.get(u, 0) + 1
            kept.append((p, o))
            if want and len(kept) >= want: break
        for p, o in kept:
            code, lic, url = LIC[p["license"]]
            login, name = people.get(o["observer_id"], ("", ""))
            name = name or login
            out.append({"species": sp, "photo_id": p["photo_id"],
                "url": f"{BASE}photos/{p['photo_id']}/medium.{p['extension'] or 'jpg'}",
                "license": lic, "author": name, "author_login": login, "observed_on": o["observed_on"],
                "source_page": f"https://www.inaturalist.org/observations/{p['observation_uuid']}",
                "attribution": f"{name}, no rights reserved (CC0)" if code == "cc0"
                               else f"© {name}, some rights reserved ({p['license']})",
                "sha256": "", "license_code": code, "license_url": url, "taxon_id": o["taxon_id"],
                "retrieved_utc": "", "snapshot_date": rows.date,
                "observation_uuid": p["observation_uuid"], "target_taxon_id": tax[o["taxon_id"].encode()][0]})
        log(f"{sp}: {len(kept)} photos, {len(n_obs)} obs, {len(n_user)} observers (of {len(cand)} candidates)")
    return out


if __name__ == "__main__":
    a = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    a.add_argument("species"); a.add_argument("out")
    a.add_argument("--source", default=BASE); a.add_argument("--cache-dir")
    a.add_argument("--want", type=int, default=0, help="photos per species, 0 = all")
    a.add_argument("--per-obs", type=int, default=0); a.add_argument("--per-observer", type=int, default=0)
    a.add_argument("--by-sa", action="store_true", help="admit CC-BY-SA (store v11+)")
    a.add_argument("--min-px", type=int, default=0, help="long-side floor of the original, px")
    a.add_argument("--coords", help="also write region coordinates (all research-grade obs)")
    a.add_argument("--max-accuracy", type=float, default=10000); a.add_argument("--min-anomaly", type=float, default=1.0)
    x = a.parse_args(); t0 = time.time()
    rows_out = curate(json.load(open(x.species)), x.source, x.cache_dir, x.want, x.per_obs, x.per_observer,
                      x.by_sa, x.min_px, x.coords, x.max_accuracy, x.min_anomaly)
    with open(x.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS); w.writeheader(); w.writerows(rows_out)
    print(f"streamed {sum(BYTES.values())/1e9:.2f} GB compressed {BYTES} in {time.time()-t0:.0f}s, "
          f"snapshot {rows.date}, {len(rows_out)} rows")
    print("CURATE_OPENDATA_DONE")
