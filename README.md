# fishial-benchmark

A reproducible, licence-clean pipeline for on-device fish identification,
built for [DeepSix Dive Log](https://deepsixdive.com): openly-licensed imagery
in, a Core ML nearest-centroid classifier out — with the benchmark that
measures it.

- **Backbone:** Meta's DINOv2 ViT-B/14 (Apache-2.0), via timm.
- **Store imagery:** iNaturalist Open Data, research-grade, CC-BY (manifest
  committed here; per-image author, licence, observation link).
- **Eval imagery:** Wikimedia Commons, revision-pinned (manifests committed) —
  a different source from the store, so the benchmark is source-disjoint.

## Result

**top-1 49% · top-5 77%** — 135 reef species, 1,010 eval images, whole-frame.
(DeepSix ships a slightly larger store that adds CC0-licensed imagery: 51%/79%.
The committed manifest reproduces the public number exactly.)

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

`curate.py` / `curate_inat.py` are the manifest builders, included so the set
can be extended to new species with the same licence discipline
(`SOURCES.md` documents the source survey and filtering rules).

## Attribution

Images are **not** in this repo and are never redistributed by it. Every
manifest row records author, exact licence string, and source page.
`manifest_inat_full_ATTRIBUTION.md` credits every contributing photographer —
including CC0 contributors, whose licence requires nothing: attribution here
is universal by policy.

## Licences

- Code: MIT.
- Imagery: per-image licences in the manifests (CC-BY for the committed store
  manifest; the Commons eval manifests carry BY/BY-SA/CC0/PD per image).
- DINOv2 weights: Meta AI, Apache-2.0, fetched at run time via timm.
