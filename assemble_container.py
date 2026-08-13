#!/usr/bin/env python3
"""Assemble the v1 clean-room model container (spec I3/I10).

  FishialModel/
    Fishial.mlmodelc   — compiled CleanRoom-6bit backbone
    labels.json        — index-ordered species array
    centroids.bin      — float32 LE (N × 768), rows L2-normalized, row i ↔ labels[i]

Zips it, prints sha256 + size for the worker manifest's GATE fields.
"""
import hashlib
import json
import pathlib
import shutil
import subprocess

import numpy as np

SRC = pathlib.Path("results_public")
OUT = pathlib.Path("container_v1")
if OUT.exists():
    shutil.rmtree(OUT)
stage = OUT / "FishialModel"
stage.mkdir(parents=True)

subprocess.run(["xcrun", "coremlcompiler", "compile", "CleanRoom-6bit.mlpackage", str(stage)], check=True)
compiled = next(stage.glob("*.mlmodelc"))
compiled.rename(stage / "Fishial.mlmodelc")

labels = json.load(open(SRC / "labels.json"))
(stage / "labels.json").write_text(json.dumps(labels, indent=0))

C = np.load(SRC / "centroids.npy").astype("<f4")
assert C.shape[1] == 768, C.shape
(stage / "centroids.bin").write_bytes(C.tobytes())

zip_path = shutil.make_archive(str(OUT / "CleanRoom-v1.mlpackage-container"), "zip", OUT, "FishialModel")
digest = hashlib.sha256(open(zip_path, "rb").read()).hexdigest()
size = pathlib.Path(zip_path).stat().st_size
print(f"container: {zip_path}")
print(f"classes: {len(labels)}  centroids: {C.shape}")
print(f"sha256: {digest}")
print(f"raw_bytes: {size}")
print("ASSEMBLE_DONE")
