#!/usr/bin/env python3
"""Download the manifest's images, verifying each against its pinned sha1.

The manifest is the dataset; the bytes are reconstructable. A sha1 mismatch
means Commons replaced the file since curation — the row is reported and
skipped, never silently substituted.

Usage: python3 fetch.py --manifest manifest_covered61.csv --out images/
"""
import argparse
import csv
import hashlib
import pathlib
import re
import time
import urllib.parse
import urllib.request

UA = "DeepSix-Fishial-Benchmark/0.1 (research curation; support@deepsixdive.com)"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--out", default="images")
    args = ap.parse_args()

    out = pathlib.Path(args.out)
    out.mkdir(exist_ok=True)
    rows = list(csv.DictReader(open(args.manifest)))
    ok = drift = 0
    for i, r in enumerate(rows):
        # Extension from the URL PATH — Commons URLs can carry ?utm query junk.
        ext = urllib.parse.urlparse(r["url"]).path.rsplit(".", 1)[-1].lower() or "img"
        safe = re.sub(r"[^A-Za-z0-9]+", "_", r["species"])
        dest = out / f"{safe}__{i}.{ext}"
        if dest.exists() and hashlib.sha1(dest.read_bytes()).hexdigest() == r["sha1"]:
            ok += 1
            continue
        data = None
        for attempt in range(5):
            req = urllib.request.Request(r["url"], headers={"User-Agent": UA})
            try:
                data = urllib.request.urlopen(req, timeout=60).read()
                break
            except Exception as e:
                # Commons rate-limits bursts; back off and retry (seen live 2026-08-12).
                if "429" in str(e) and attempt < 4:
                    time.sleep(30 * (attempt + 1))
                    continue
                print(f"FETCH FAIL {r['file_title']}: {e}")
                break
        if data is None:
            continue
        if hashlib.sha1(data).hexdigest() != r["sha1"]:
            print(f"SHA1 DRIFT (Commons replaced the file): {r['file_title']}")
            drift += 1
            continue
        dest.write_bytes(data)
        ok += 1
        time.sleep(0.5)
    print(f"fetched+verified {ok}/{len(rows)}; drifted {drift}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
