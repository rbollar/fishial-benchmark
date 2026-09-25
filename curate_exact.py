#!/usr/bin/env python3
"""#2075: curate_inat.py with an EXACT taxon. `taxon_name=` is a loose match
that pulled other animals into shipped classes; this resolves the species'
taxon_id first and drops any observation whose taxon isn't the species or a
subspecies of it. Same ordering (votes), licences and manifest columns."""
import csv, json, sys, time, urllib.parse, urllib.request
UA = "DeepSix-Fishial-Benchmark/0.1 (research curation; support@deepsixdive.com)"
OK = {"cc0", "cc-by"}
def api(path):
    return json.load(urllib.request.urlopen(urllib.request.Request(
        "https://api.inaturalist.org/v1/" + path, headers={"User-Agent": UA}), timeout=60))
def taxon_id(name):
    hits = [t for t in api("taxa?rank=species&per_page=30&q=" + urllib.parse.quote(name))["results"] if t["name"] == name]
    if not hits: sys.exit(f"no exact iNat taxon for {name}")
    return hits[0]["id"]
def photos_for(species, want):
    tid, out, page = taxon_id(species), [], 1
    while len(out) < want and page <= 5:
        res = api(f"observations?taxon_id={tid}&quality_grade=research&photo_license=cc0,cc-by&per_page=100&page={page}&order_by=votes")["results"]
        if not res: break
        for obs in res:
            t = (obs.get("taxon") or {}).get("name", "")
            if not (t == species or t.startswith(species + " ")) or "×" in t: continue
            login = (obs.get("user") or {}).get("login", ""); name = (obs.get("user") or {}).get("name") or login
            for ph in obs.get("photos", []):
                lic = (ph.get("license_code") or "").lower()
                if lic not in OK: continue
                ext = (ph.get("url") or "jpg").rsplit(".", 1)[-1].split("?")[0] or "jpg"
                out.append({"species": species, "photo_id": ph["id"],
                    "url": f"https://inaturalist-open-data.s3.amazonaws.com/photos/{ph['id']}/medium.{ext}",
                    "license": "CC0" if lic == "cc0" else "CC-BY 4.0", "author": name, "author_login": login,
                    "observed_on": obs.get("observed_on") or "",
                    "source_page": f"https://www.inaturalist.org/observations/{obs['id']}",
                    "attribution": f"{name}, no rights reserved (CC0)" if lic == "cc0" else f"© {name}, some rights reserved (CC-BY)",
                    "taxon": t})
                if len(out) >= want: break
            if len(out) >= want: break
        page += 1; time.sleep(1.2)
    return out
if __name__ == "__main__":
    species, want, dest = json.load(open(sys.argv[1])), int(sys.argv[2]), sys.argv[3]
    rows = []
    for s in species:
        got = photos_for(s, want); rows += got; print(f"{s}: {len(got)}", flush=True); time.sleep(1.2)
    with open(dest, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    print("CURATE_EXACT_DONE")
