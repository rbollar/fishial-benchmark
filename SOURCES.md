# Fish image sources beyond Wikimedia Commons — BY / BY-SA / PD only

Recorded 2026-08-12 (Rick). For the DeepSix classifier evaluation image set
(manifest + fetch script, per-image attribution). Licenses verified from live
sources on this date.

## Ranked sources

1. **iNaturalist Open Data (AWS S3)** — bucket contains only CC0 / CC-BY / CC-BY-NC photos; per-photo license, observer name/login, and taxon in metadata CSVs. **Filter to CC0 + CC-BY.** Stable fetch URLs: `https://inaturalist-open-data.s3.amazonaws.com/photos/{photo_id}/medium.{ext}` (sizes: original/large/medium/small/thumb/square). Attribution format: CC0 → "{name}, no rights reserved (CC0)"; else "© {name}, some rights reserved ({license})". Docs: https://github.com/inaturalist/inaturalist-open-data · https://registry.opendata.aws/inaturalist-open-data/
2. **GBIF occurrence media API** — aggregates iNat, museums, Naturalis, etc. Per-media license field; downloads are DOI-citable (cite the DOI in the public repo). **Caveat:** license search filter has returned CC-BY-SA under a CC-BY query (gbif/portal-feedback#3831) — always re-verify the license field per record client-side. https://techdocs.gbif.org/en/openapi/
3. **ALA — Atlas of Living Australia** — Australian bias matches DeepSix audience; per-image license via images.ala.org, heavily CC-BY.
4. **OzFish (AIMS)** — CC-BY 3.0 AU. ~80k fish crops, ~45k bboxes, 507 species, Australian BRUVS video frames; species-level taxonomy on crops/frames (basic bboxes are fish/no-fish only). Hosted on Pawsey. Domain shift: bait-cam frames, not diver photos. https://github.com/open-AIMS/ozfish
5. **NOAA (Photo Library, NOAA Fisheries)** — US Government public domain. No species-labelled bulk API; manual harvest, low volume.
6. **Smithsonian Open Access** — CC0, bulk metadata (https://github.com/Smithsonian/OpenAccess). Division of Fishes = preserved specimens; large domain shift — rare-species gap-fill only.
7. **FathomNet** — per-contributor CC0/CC-BY/CC-BY-NC/CC-BY-ND, filterable; mostly MBARI deep-sea ROV imagery, little reef overlap. Data-use policy says database imagery is "intended solely for ML training." https://www.fathomnet.org/datause

## Excluded

- **FishBase** — predominantly CC-BY-NC or unlabelled.
- **EOL** — aggregator with per-item licenses; mostly superseded by GBIF for this purpose.
- **Flickr CC search** — license-filterable but species labels unreliable; not worth the curation cost.

## Edge cases

- **Train/test contamination:** Fishial's training corpus (2.6M images) plausibly overlaps iNat/GBIF material. For evaluation, filter iNat observations to dates after the v0.10.2 checkpoint (repo HEAD 2026-04-09 as proxy), and treat Rick's own dive photos as the uncontaminated gold set.
- **License string fidelity:** record the exact per-image license (e.g. "CC-BY 3.0 AU" for OzFish, not normalized "BY") — 3.0 attribution mechanics differ slightly from 4.0.
- **docs.fishial.ai** has a "Fish images sites" page (`/otherprojects/fishimagedatasets`) and an external-datasets page (`/otherprojects/externalfishdatasets`) — both unreachable 2026-08-12; check when the docs site returns, both for additional sources and as a hint at what their training corpus drew from (contamination assessment).

## Consequence for the clean-room store (I10)

Commons built tonight's ~130-class store (3–12 imgs/species). **iNaturalist Open
Data (CC0+CC-BY, post-2026-04 for eval sets) is the v1.1 path to 20–50
imgs/species and hundreds more species** — richer centroids where tonight's
held-outs are weakest, with the same manifest/fetch/attribution discipline.
