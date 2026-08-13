#!/usr/bin/env python3
"""Wikimedia Commons ground-truth curation for the Fishial benchmark (D14/D15).

For each target species (the Fishial-covered intersection from the Phase 1
coverage audit), query Commons for images, keep only compatible licences
(CC BY-SA / CC BY / CC0 / PD), and emit a manifest that pins each image by
sha1 so the set is frozen and reproducible without redistributing bytes.

Manifest columns:
  species, file_title, url, sha1, width, height, author, license,
  source_page, shot_type_guess

shot_type_guess is a heuristic (in_situ / aquarium / specimen / unknown) from
categories + description keywords — a human pass upgrades it before scoring;
the benchmark stratifies on it (D14 caveat: Commons leans specimen-style).

Usage:
  python3 curate.py --species coverage_rick.json --per-species 3 [--limit-species 5]
"""
import argparse
import csv
import json
import re
import time
import urllib.parse
import urllib.request

API = "https://commons.wikimedia.org/w/api.php"
UA = "DeepSix-Fishial-Benchmark/0.1 (research curation; support@deepsixdive.com)"

OK_LICENSES = re.compile(
    r"^(cc[ -]?by([ -]sa)?[ -]?[1-4]\.[05]|cc0|public domain|pd)", re.I)

IN_SITU = re.compile(r"underwater|in situ|diving|scuba|reef|snorkel", re.I)
AQUARIUM = re.compile(r"aquarium|zoo|tank|captiv", re.I)
SPECIMEN = re.compile(r"specimen|museum|market|caught|catch|fishing|dead|preserved|taxidermy", re.I)


def api(params: dict) -> dict:
    params = {**params, "format": "json"}
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def shot_type(text: str) -> str:
    if IN_SITU.search(text):
        return "in_situ"
    if AQUARIUM.search(text):
        return "aquarium"
    if SPECIMEN.search(text):
        return "specimen"
    return "unknown"


def images_for_species(species: str, want: int) -> list[dict]:
    """Category members first (Commons categories are named by binomial),
    falling back to search. Licence-filtered; prefers in_situ shot types."""
    titles: list[str] = []
    cat = api({
        "action": "query", "list": "categorymembers",
        "cmtitle": f"Category:{species}", "cmtype": "file", "cmlimit": 50,
    }).get("query", {}).get("categorymembers", [])
    titles += [m["title"] for m in cat]
    if len(titles) < want * 3:
        hits = api({
            "action": "query", "list": "search", "srnamespace": 6,
            "srsearch": f'"{species}"', "srlimit": 30,
        }).get("query", {}).get("search", [])
        titles += [h["title"] for h in hits if h["title"] not in titles]

    out = []
    for batch_start in range(0, len(titles), 20):
        batch = titles[batch_start:batch_start + 20]
        if not batch:
            break
        info = api({
            "action": "query", "titles": "|".join(batch),
            "prop": "imageinfo|categories",
            "iiprop": "url|sha1|size|extmetadata", "cllimit": 20,
        }).get("query", {}).get("pages", {})
        for page in info.values():
            ii = (page.get("imageinfo") or [{}])[0]
            meta = ii.get("extmetadata", {})
            lic = meta.get("LicenseShortName", {}).get("value", "")
            if not OK_LICENSES.match(lic.strip()):
                continue
            if ii.get("width", 0) < 300:
                continue  # thumbnails/icons are useless to the model
            cats = " ".join(c["title"] for c in page.get("categories", []))
            desc = re.sub(r"<[^>]+>", "", meta.get("ImageDescription", {}).get("value", ""))
            author = re.sub(r"<[^>]+>", "", meta.get("Artist", {}).get("value", "")).strip()
            out.append({
                "species": species,
                "file_title": page.get("title", ""),
                "url": ii.get("url", ""),
                "sha1": ii.get("sha1", ""),
                "width": ii.get("width", 0),
                "height": ii.get("height", 0),
                "author": author,
                "license": lic,
                "source_page": ii.get("descriptionurl", ""),
                "shot_type_guess": shot_type(cats + " " + desc),
            })
        time.sleep(1)  # polite: 1 rps
    # in_situ first, then unknown, then the rest; bigger images win ties
    rank = {"in_situ": 0, "unknown": 1, "aquarium": 2, "specimen": 3}
    out.sort(key=lambda r: (rank[r["shot_type_guess"]], -r["width"]))
    return out[:want]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--species", required=True,
                    help="coverage JSON ({covered:[...]}) or newline list")
    ap.add_argument("--per-species", type=int, default=3)
    ap.add_argument("--limit-species", type=int, default=0)
    ap.add_argument("--out", default="manifest.csv")
    args = ap.parse_args()

    if args.species.endswith(".json"):
        species = json.load(open(args.species))["covered"]
    else:
        species = [l.strip() for l in open(args.species) if l.strip()]
    if args.limit_species:
        species = species[:args.limit_species]

    rows, misses = [], []
    for i, sp in enumerate(species, 1):
        got = images_for_species(sp, args.per_species)
        rows += got
        if not got:
            misses.append(sp)
        print(f"[{i}/{len(species)}] {sp}: {len(got)} image(s)"
              + (f" ({sum(1 for g in got if g['shot_type_guess'] == 'in_situ')} in-situ)" if got else ""))
        time.sleep(1)

    with open(args.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ["species"])
        w.writeheader()
        w.writerows(rows)
    print(f"\n{len(rows)} images across {len(species) - len(misses)}/{len(species)} species → {args.out}")
    if misses:
        print("no licence-compatible images:", ", ".join(misses))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
