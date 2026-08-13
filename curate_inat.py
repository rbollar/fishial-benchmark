#!/usr/bin/env python3
"""iNaturalist Open Data curation (SOURCES.md #1) — v1.1 centroid store.

Discovery via the iNat API (research-grade, CC0/CC-BY only), media URLs
constructed for the Open Data S3 bucket. Records the EXACT per-photo licence
string and SOURCES.md-format attribution. `observed_on` is kept so eval
subsets can be date-filtered (post-2026-04 = post-Fishial-checkpoint).

Usage: python3 curate_inat.py --species labels.json --per-species 30 --out manifest_inat.csv
"""
import argparse
import csv
import json
import time
import urllib.parse
import urllib.request

API = "https://api.inaturalist.org/v1/observations"
UA = "DeepSix-Fishial-Benchmark/0.1 (research curation; support@deepsixdive.com)"
OK = {"cc0", "cc-by"}


def api(params):
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except Exception as e:
            if ("429" in str(e) or "503" in str(e)) and attempt < 3:
                time.sleep(30 * (attempt + 1))
                continue
            raise


def photos_for(species, want):
    out, page = [], 1
    while len(out) < want and page <= 3:
        data = api({
            "taxon_name": species, "quality_grade": "research",
            "photo_license": "cc0,cc-by", "per_page": 100, "page": page,
            "order_by": "votes",
        })
        results = data.get("results", [])
        if not results:
            break
        for obs in results:
            login = (obs.get("user") or {}).get("login", "")
            name = (obs.get("user") or {}).get("name") or login
            when = obs.get("observed_on") or ""
            for ph in obs.get("photos", []):
                lic = (ph.get("license_code") or "").lower()
                if lic not in OK:
                    continue
                pid = ph.get("id")
                ext = (ph.get("url") or "jpg").rsplit(".", 1)[-1].split("?")[0] or "jpg"
                attribution = (f"{name}, no rights reserved (CC0)" if lic == "cc0"
                               else f"© {name}, some rights reserved (CC-BY)")
                out.append({
                    "species": species,
                    "photo_id": pid,
                    "url": f"https://inaturalist-open-data.s3.amazonaws.com/photos/{pid}/medium.{ext}",
                    "license": "CC0" if lic == "cc0" else "CC-BY 4.0",
                    "author": name,
                    "author_login": login,
                    "observed_on": when,
                    "source_page": f"https://www.inaturalist.org/observations/{obs.get('id')}",
                    "attribution": attribution,
                })
                if len(out) >= want:
                    break
            if len(out) >= want:
                break
        page += 1
        time.sleep(1.2)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--species", required=True, help="JSON array or newline list")
    ap.add_argument("--per-species", type=int, default=30)
    ap.add_argument("--out", default="manifest_inat.csv")
    args = ap.parse_args()

    text = open(args.species).read()
    species = json.loads(text) if text.lstrip().startswith("[") else [l.strip() for l in text.splitlines() if l.strip()]

    rows, misses = [], []
    for i, sp in enumerate(species, 1):
        got = photos_for(sp, args.per_species)
        rows += got
        if not got:
            misses.append(sp)
        print(f"[{i}/{len(species)}] {sp}: {len(got)}")
        time.sleep(1.2)

    with open(args.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"\n{len(rows)} photos across {len(species) - len(misses)}/{len(species)} species → {args.out}")
    if misses:
        print("no licence-compatible photos:", ", ".join(misses))
    print("INAT_CURATE_DONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
