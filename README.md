# fishial-benchmark

A reproducible, licence-clean pipeline for on-device fish identification,
built for [DeepSix Dive Log](https://deepsixdive.com): openly-licensed imagery
in, a Core ML nearest-centroid classifier out — with the benchmark that
measures it.

- **Backbone:** Meta's DINOv2 ViT-B/14 (Apache-2.0), via timm.
- **Store imagery:** iNaturalist Open Data, research-grade, CC0 and CC-BY
  (manifests committed here list every photo in the shipped store, with
  per-image author, license, observation link).
- **Eval imagery:** Wikimedia Commons, revision-pinned (manifests committed) —
  a different source from the store, so the benchmark is source-disjoint.

## Result

**top-1 49% · top-5 77%** — 135 reef species, 1,010 eval images, whole-frame.
The published number is built from the manifest's CC-BY rows, and
`public_subset.py` reproduces it exactly. The manifest also carries the
CC0 rows that DeepSix's store adds (51%/79% as measured for the shipped
store); `public_subset.py --with-cc0` builds from every row.

## Reproduce

```
# 1. Eval set — Wikimedia Commons, pinned by sha1
python3 fetch.py --manifest manifest_covered61.csv  --out images
python3 fetch.py --manifest manifest_uncovered79.csv --out images_uncovered

# 2. (macOS) salient-object crops for the eval images
swiftc -O vision_crop.swift -o vision_crop
./vision_crop images images_cropped
./vision_crop images_uncovered images_uncovered_cropped

# 3. Store imagery — iNaturalist Open Data
python3 fetch_inat.py manifest_inat_full_public.csv images_inat

# 4. Build the store, score the eval, save the artifacts
python3 public_subset.py

# 5. Core ML: convert the backbone, assemble the model container
python3 convert_dinov2.py
python3 assemble_container.py
```

`curate.py` builds the Commons eval manifests. For iNaturalist store imagery,
see "Discovery from iNaturalist Open Data" below; `curate_inat.py` /
`curate_exact.py` are the older API-paging builders, kept so past manifests
can be regenerated. `SOURCES.md` documents the source survey and filtering rules.


**Photographer cap (default).** `curate_opendata.py` limits how many photos one photographer contributes to a species, scaled to supply: 25% of the target when supply is under 2x, 20% up to 5x, 10% beyond (never below 2). A species' reference is the mean of its photos, so one prolific photographer would otherwise make it the mean of their camera, site and subject. A cap that would push a species below 30 photos is relaxed one photo at a time and logged. `--per-observer N` sets a fixed cap; `--per-observer 0` turns it off.

## Discovery from iNaturalist Open Data (recommended)

For more than a handful of species, don't page the iNaturalist API. iNaturalist
publishes the metadata monthly as four tab-separated tables in the public
bucket (`https://inaturalist-open-data.s3.amazonaws.com/{taxa,observations,photos,observers}.csv.gz`,
~33 GB compressed; dated tarballs under `metadata/`). The same data is on GBIF as
DOI [10.15468/ab3s5x](https://doi.org/10.15468/ab3s5x), which carries versioned
licence URLs but omits CC BY-SA observations and photo dimensions.

```
# 1. Discovery: stream the tables, keep research-grade CC0 / CC-BY photos of
#    each taxon and its descendants (hybrids dropped). --cache-dir keeps the
#    tables for the next run; without it nothing but the matches is written.
python3 curate_opendata.py species.json pool.csv --cache-dir opendata --coords coords.tsv
#    species.json = {"Holacanthus ciliaris": 47235, ...} (exact iNat taxon ids)
#    --want N --per-obs 2 --per-observer K cap the pool; --by-sa admits CC BY-SA.

# 2. Choose your final set from pool.csv (your own curation).

# 3. Re-check ONLY the final set against the live API (<=200 observations per
#    call, ~1 req/s): current licence, still research grade, still the taxon,
#    no hybrid identification or mention. Adds the integer observation id and
#    license_checked_utc.
python3 verify_selection.py final.csv final_verified.csv --drops drops.json

# 4. Fetch as before
python3 fetch_inat.py final_verified.csv images_new
```

The manifest columns are the same as the published `manifest_*_public.csv`
files, plus `snapshot_date`, `observation_uuid` and `target_taxon_id`.
The licence discipline is unchanged: CC0 and CC BY only (CC BY-SA only if your
use admits share-alike), never NC or ND, and every row keeps author, login,
licence and source page. The snapshot can be a month old and a photographer
can relicense at any time, so step 3 is not optional: a photo relicensed to
NC/ND or all-rights-reserved since the snapshot is dropped, not used.
Rate limits for step 3: about 1 request per second and well under 10,000 a
day, with a User-Agent that names you. Tests: `python3 -m unittest`.

## Attribution

Images are **not** in this repo and are never redistributed by it. Every
manifest row records author, exact licence string, and source page.
The `manifest_*_public.csv` files list every iNaturalist photo in each
store cut, CC0 rows included, and CC0 photos are credited the way
iNaturalist suggests: "Name, no rights reserved (CC0)".
`manifest_inat_full_ATTRIBUTION.md` credits every contributing photographer —
including CC0 contributors, whose licence requires nothing: attribution here
is universal by policy.

## Licences

- Code: MIT.
- Imagery: per-image licenses in the manifests (CC0 or CC-BY 4.0 per row in
  the store manifests; the Commons eval manifests carry BY/BY-SA/CC0/PD per image).
- DINOv2 weights: Meta AI, Apache-2.0, fetched at run time via timm.
