#!/usr/bin/env python3
"""Fetch iNat Open Data media; records sha256 post-download (S3 is immutable
per photo_id, so the recorded hash pins the set for reproducibility)."""
import csv, hashlib, pathlib, re, sys, time, urllib.request
UA = "DeepSix-Fishial-Benchmark/0.1 (research curation; support@deepsixdive.com)"
manifest, outdir = sys.argv[1], pathlib.Path(sys.argv[2])
outdir.mkdir(exist_ok=True)
rows = list(csv.DictReader(open(manifest)))
ok = 0
for i, r in enumerate(rows):
    safe = re.sub(r"[^A-Za-z0-9]+", "_", r["species"])
    dest = outdir / f"{safe}__{i}.jpg"
    r["sha256"] = ""
    if dest.exists():
        r["sha256"] = hashlib.sha256(dest.read_bytes()).hexdigest(); ok += 1; continue
    try:
        req = urllib.request.Request(r["url"], headers={"User-Agent": UA})
        data = urllib.request.urlopen(req, timeout=60).read()
    except Exception as e:
        print(f"FAIL {r['photo_id']}: {e}"); continue
    dest.write_bytes(data)
    r["sha256"] = hashlib.sha256(data).hexdigest()
    ok += 1
    if i % 200 == 0: print(f"fetched {i}/{len(rows)}")
    time.sleep(0.25)
with open(manifest.replace(".csv", "_pinned.csv"), "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader(); w.writerows(rows)
print(f"fetched {ok}/{len(rows)}"); print("FETCH_INAT_DONE")
