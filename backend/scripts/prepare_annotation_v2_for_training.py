#!/usr/bin/env python3
"""
Prepare annotation_v2 for 05_binary_training:

1. Build *_raw.npy from JPG/PNG patch images
2. Rebuild masks/*_mask.png from LabelMe JSON (notebook Cell 3 rules)
3. Sync into TLBC_DSM_DTM/annotation_v2 (path used by 05 notebook)

Canal-positive labels: canal, channel, distributary, minor
Everything else (fic, not canal, other, ...) stays background (0).
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

SRC = Path(r"D:\Github\Canal Pipeline\annotation_v2")
DST = Path(r"D:\Github\Canal Pipeline\TLBC_DSM_DTM\annotation_v2")

CANAL_LABELS = {"canal", "channel", "distributary", "minor"}


def load_rgb(path: Path) -> np.ndarray:
    return np.array(Image.open(path).convert("RGB"), dtype=np.uint8)


def build_raw_npy(anno: Path) -> int:
    created = 0
    for img in list(anno.glob("*.jpg")) + list(anno.glob("*.png")):
        if img.name.endswith("_full.jpg") or img.name.endswith("_mask.png"):
            continue
        if img.parent.name == "masks":
            continue
        stem = img.stem
        npy = anno / f"{stem}_raw.npy"
        if npy.exists():
            continue
        np.save(npy, load_rgb(img))
        created += 1
    return created


def rebuild_masks(anno: Path) -> dict:
    mask_dir = anno / "masks"
    mask_dir.mkdir(parents=True, exist_ok=True)
    stats = {"json": 0, "with_canal": 0, "empty": 0, "written": 0}

    for jf in sorted(anno.glob("*.json")):
        if jf.name.endswith("_meta.json"):
            continue
        anno_data = json.loads(jf.read_text(encoding="utf-8"))
        h = int(anno_data.get("imageHeight") or 512)
        w = int(anno_data.get("imageWidth") or 512)
        # Prefer actual image size when present
        stem = jf.stem
        for ext in (".png", ".jpg"):
            img_path = anno / f"{stem}{ext}"
            if img_path.exists():
                im = Image.open(img_path)
                w, h = im.size
                break

        mask = np.zeros((h, w), dtype=np.uint8)
        has_canal = False
        for shape in anno_data.get("shapes", []):
            lbl = shape["label"].lower().strip()
            if lbl not in CANAL_LABELS:
                continue
            pts = np.array(shape["points"], dtype=np.int32)
            st = shape.get("shape_type", "polygon")
            if st == "polygon":
                cv2.fillPoly(mask, [pts], 1)
            elif st == "rectangle" and len(pts) >= 2:
                cv2.rectangle(mask, tuple(pts[0]), tuple(pts[1]), 1, -1)
            elif st == "line":
                cv2.polylines(mask, [pts], False, 1, thickness=5)
            has_canal = True

        out = mask_dir / f"{stem}_mask.png"
        cv2.imwrite(str(out), mask * 255)
        stats["json"] += 1
        stats["written"] += 1
        if has_canal:
            stats["with_canal"] += 1
        else:
            stats["empty"] += 1
    return stats


def count_pairs(anno: Path) -> tuple[int, int, int]:
    masks = anno / "masks"
    pairs = pos = neg = 0
    for mf in masks.glob("*_mask.png"):
        bn = mf.name.replace("_mask.png", "")
        raw = anno / f"{bn}_raw.npy"
        if not raw.exists():
            continue
        m = cv2.imread(str(mf), cv2.IMREAD_GRAYSCALE)
        if m is None:
            continue
        pairs += 1
        if m.max() > 0:
            pos += 1
        else:
            neg += 1
    return pairs, pos, neg


def sync(src: Path, dst: Path) -> None:
    dst.mkdir(parents=True, exist_ok=True)
    (dst / "masks").mkdir(parents=True, exist_ok=True)
    for pattern in ("*.jpg", "*.png", "*.json", "*_raw.npy"):
        for f in src.glob(pattern):
            if f.name.endswith("_full.jpg"):
                continue
            shutil.copy2(f, dst / f.name)
    for f in (src / "masks").glob("*.png"):
        shutil.copy2(f, dst / "masks" / f.name)


def main() -> None:
    print(f"Source: {SRC}")
    n = build_raw_npy(SRC)
    print(f"Created raw.npy from images: {n}")
    stats = rebuild_masks(SRC)
    print(f"Mask rebuild: {stats}")
    pairs, pos, neg = count_pairs(SRC)
    print(f"Pairs source: total={pairs} positive={pos} negative={neg}")

    print(f"Sync -> {DST}")
    sync(SRC, DST)
    pairs2, pos2, neg2 = count_pairs(DST)
    print(f"Pairs notebook path: total={pairs2} positive={pos2} negative={neg2}")
    if pos2 < 1:
        raise SystemExit("No positive canal masks — cannot train binary model")
    print("READY for 05 binary training")


if __name__ == "__main__":
    main()
