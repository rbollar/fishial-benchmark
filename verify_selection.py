#!/usr/bin/env python3
"""Re-check a FINAL selection against the live iNaturalist API before use.

The Open Data snapshot can be ~31 days old. For each selected row this re-reads
the observation (batched, <=200 per call by uuid, ~1 req/s) and drops the row if:
  - the observation is gone, private, or no longer research grade;
  - its taxon is no longer the target or a descendant of it, or is a hybrid;
  - any identification (current or withdrawn) names a hybrid, or the description,
    a comment or an identification remark mentions one (the v10 Holacanthus rule);
  - the photo is no longer on it, or its CURRENT licence is outside the allowed
    set (a photo relicensed to NC/ND/all-rights-reserved is never used).
Kept rows get the integer observation id in source_page, the current licence
and observer name, and license_checked_utc.

    python3 verify_selection.py selection.csv verified.csv [--by-sa] [--drops drops.json]

Run it over the final selection only (tens of calls), not over a discovery pool.
"""
import argparse, csv, json, re, sys, time, urllib.request
from curate_opendata import LIC, UA

API = "https://api.inaturalist.org/v1/observations?per_page=200&uuid="
HYBRID = re.compile(r"hybrid", re.I)


def fetch_json(url):  # replaced in tests
    return json.load(urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=60))


def hybrid_mention(o):
    if any("×" in (i.get("taxon") or {}).get("name", "") or (i.get("taxon") or {}).get("rank") == "hybrid"
           for i in o.get("identifications") or []):
        return True
    texts = [o.get("description") or ""] + [c.get("body") or "" for c in o.get("comments") or []] \
        + [i.get("body") or "" for i in o.get("identifications") or []]
    return any(HYBRID.search(t) for t in texts)


def verify(rows, by_sa=False, pause=1.1, now=None):
    ok = {"cc0", "cc-by"} | ({"cc-by-sa"} if by_sa else set())
    uuids = sorted({r["observation_uuid"] for r in rows})
    live = {}
    for i in range(0, len(uuids), 200):
        for o in fetch_json(API + ",".join(uuids[i:i + 200]))["results"]:
            live[o["uuid"]] = o
        if i + 200 < len(uuids): time.sleep(pause)
    now = now or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    kept, drops = [], []
    for r in rows:
        o = live.get(r["observation_uuid"])
        tx = (o or {}).get("taxon") or {}
        tid = int(r["target_taxon_id"])
        ph = next((p for p in (o or {}).get("photos", []) if str(p["id"]) == r["photo_id"]), None)
        lic = ((ph or {}).get("license_code") or "none").lower()
        why = ("observation gone" if not o else
               "not research grade" if o.get("quality_grade") != "research" else
               "taxon moved" if not (tx.get("id") == tid or tid in (tx.get("ancestor_ids") or [])) else
               "hybrid taxon" if "×" in tx.get("name", "") or tx.get("rank") == "hybrid" else
               "hybrid mention" if hybrid_mention(o) else
               "photo removed" if not ph else
               f"licence now {lic}" if lic not in ok else None)
        if why:
            drops.append({"photo_id": r["photo_id"], "observation_uuid": r["observation_uuid"],
                          "species": r["species"], "reason": why, "obs": (o or {}).get("id")})
            continue
        u = o.get("user") or {}
        login = u.get("login") or r["author_login"]; name = u.get("name") or login
        code, label, url = next(v for v in LIC.values() if v[0] == lic)
        r = dict(r, license=label, license_code=code, license_url=url, author=name, author_login=login,
                 taxon_id=str(tx["id"]), source_page=f"https://www.inaturalist.org/observations/{o['id']}",
                 attribution=f"{name}, no rights reserved (CC0)" if code == "cc0"
                             else f"© {name}, some rights reserved ({code.upper()})",
                 license_checked_utc=now)
        kept.append(r)
    return kept, drops


if __name__ == "__main__":
    a = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    a.add_argument("selection"); a.add_argument("out")
    a.add_argument("--by-sa", action="store_true"); a.add_argument("--drops")
    x = a.parse_args()
    rows = list(csv.DictReader(open(x.selection)))
    kept, drops = verify(rows, x.by_sa)
    with open(x.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(dict.fromkeys(list(rows[0]) + ["license_checked_utc"])))
        w.writeheader(); w.writerows(kept)
    if x.drops: json.dump(drops, open(x.drops, "w"), indent=1)
    for d in drops: print("DROP", d["species"], d["photo_id"], d["reason"])
    print(f"kept {len(kept)}/{len(rows)}, dropped {len(drops)}"); print("VERIFY_DONE")
