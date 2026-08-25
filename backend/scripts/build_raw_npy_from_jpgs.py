#!/usr/bin/env python3
"""
Rebuild missing *_raw.npy files from existing LabelMe JPG patches.

Notebook 05_binary_training only trains on (mask.png + *_raw.npy) pairs.
Your annotation_v2 has JPG + JSON + masks but zero *_raw.npy, so training
sees 0 samples and never writes best_binary_unet_v5.pth.

This script does NOT re-extract from orthos and does NOT overwrite labels.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import numpy as np
from PIL import Image

# Real labeled data lives here (project root annotation_v2)
SRC_ANNO = Path(r"D:\Github\Canal Pipeline\annotation_v2")
# Notebook 05 looks here (DATA_DIR/annotation_v2)
DST_ANNO = Path(r"D:\Github\Canal Pipeline\TLBC_DSM_DTM\annotation_v2")


def jpg_to_raw_npy(anno_dir: Path) -> tuple[int, int]:
    created = 0
    skipped = 0
    for jpg in sorted(anno_dir.glob("*.jpg")):
        if jpg.name.endswith("_full.jpg"):
            continue
        stem = jpg.stem
        npy = anno_dir / f"{stem}_raw.npy"
        if npy.exists():
            skipped += 1
            continue
        rgb = np.array(Image.open(jpg).convert("RGB"), dtype=np.uint8)
        np.save(npy, rgb)
        created += 1
        if created % 25 == 0:
            print(f"  created {created} npy ...")
    return created, skipped


def sync_tree(src: Path, dst: Path) -> None:
    dst.mkdir(parents=True, exist_ok=True)
    (dst / "masks").mkdir(parents=True, exist_ok=True)

    for pattern in ("*.jpg", "*.json", "*_raw.npy"):
        for f in src.glob(pattern):
            if f.name.endswith("_full.jpg"):
                continue
            target = dst / f.name
            if not target.exists() or target.stat().st_size != f.stat().st_size:
                shutil.copy2(f, target)

    src_masks = src / "masks"
    if src_masks.is_dir():
        for f in src_masks.glob("*.png"):
            target = dst / "masks" / f.name
            if not target.exists() or target.stat().st_size != f.stat().st_size:
                shutil.copy2(f, target)


def count_pairs(anno_dir: Path) -> int:
    masks = anno_dir / "masks"
    if not masks.is_dir():
        return 0
    n = 0
    for mf in masks.glob("*_mask.png"):
        basename = mf.name.replace("_mask.png", "")
        if (anno_dir / f"{basename}_raw.npy").is_file():
            n += 1
    return n


def main() -> None:
    if not SRC_ANNO.is_dir():
        raise SystemExit(f"Missing annotation folder: {SRC_ANNO}")

    print(f"Source: {SRC_ANNO}")
    created, skipped = jpg_to_raw_npy(SRC_ANNO)
    print(f"JPG -> raw.npy: created={created}, already_present={skipped}")

    print(f"Syncing into notebook path: {DST_ANNO}")
    sync_tree(SRC_ANNO, DST_ANNO)
    # Also ensure npy exist on destination if only jpg were copied earlier
    c2, s2 = jpg_to_raw_npy(DST_ANNO)
    print(f"Dest JPG -> raw.npy: created={c2}, already_present={s2}")

    pairs_src = count_pairs(SRC_ANNO)
    pairs_dst = count_pairs(DST_ANNO)
    print(f"Trainable pairs (mask+raw): source={pairs_src}, notebook_path={pairs_dst}")
    if pairs_dst == 0:
        raise SystemExit("Still 0 pairs — masks or npy missing")
    print("OK — annotation_v2 is ready for 05_binary_training Cell 4")


if __name__ == "__main__":
    main()
