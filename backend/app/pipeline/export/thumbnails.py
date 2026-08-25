from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import rasterio
from rasterio.windows import Window
from PIL import Image

from app.pipeline.processing.preprocessing import contrast_stretch


def _enhance(rgb: np.ndarray, valid: np.ndarray | None) -> np.ndarray:
    f = rgb.astype(np.float32)
    for ch in range(3):
        pv = f[:, :, ch][valid] if valid is not None else f[:, :, ch].ravel()
        if pv.size:
            lo, hi = np.percentile(pv, [2, 98])
            f[:, :, ch] = np.clip((f[:, :, ch] - lo) / (hi - lo + 1e-6) * 255, 0, 255)
    return np.ascontiguousarray(f.astype(np.uint8))


def write_reach_thumbnails(
    orthophoto_path: str,
    reaches: list[dict],
    labels_s: np.ndarray | None,
    ds: int,
    out_dir: Path,
) -> dict[str, str]:
    """Write images/0001.jpg … and return reach_id -> relative path images/NNNN.jpg."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rel: dict[str, str] = {}
    with rasterio.open(orthophoto_path) as src:
        for seq, reach in enumerate(reaches, start=1):
            rid = str(reach.get("global_reach_idx", reach.get("reach_idx", seq - 1)))
            fname = f"{seq:04d}.jpg"
            dest = out_dir / fname
            rgb = _crop_reach(src, reach, labels_s, ds)
            if rgb is None:
                continue
            Image.fromarray(rgb).save(dest, quality=88)
            rel[rid] = f"images/{fname}"
            reach["thumbnail_relpath"] = rel[rid]
    return rel


def _crop_reach(src, reach: dict, labels_s, ds: int) -> np.ndarray | None:
    if reach.get("bbox_px"):
        r0, a0, r1, a1 = reach["bbox_px"]
        rh, rw = r1 - r0, a1 - a0
        if rh < 4 or rw < 4:
            return None
        bands = [1, 2, 3, 4] if src.count >= 4 else [1, 2, 3]
        d = src.read(bands, window=Window(a0, r0, rw, rh))
        rgb = np.transpose(d[:3], (1, 2, 0))
        valid = d[3] == 255 if src.count >= 4 else None
        crop = _enhance(rgb, valid)
        if max(rh, rw) > 1100:
            sc = 1100 / max(rh, rw)
            crop = cv2.resize(crop, (max(1, int(rw * sc)), max(1, int(rh * sc))), interpolation=cv2.INTER_AREA)
        return crop

    if "bbox" not in reach:
        return None
    r_min, c_min, r_max, c_max = reach["bbox"]
    fr_min, fc_min = r_min * ds, c_min * ds
    fr_max = min(r_max * ds, src.height)
    fc_max = min(c_max * ds, src.width)
    rh, rw = fr_max - fr_min, fc_max - fc_min
    if rh < 4 or rw < 4:
        return None
    data = src.read([1, 2, 3], window=Window(fc_min, fr_min, rw, rh))
    rgb = data.transpose(1, 2, 0)
    if max(rh, rw) > 400:
        sc2 = 400 / max(rh, rw)
        rgb = cv2.resize(rgb, (max(1, int(rw * sc2)), max(1, int(rh * sc2))), interpolation=cv2.INTER_AREA)
    return contrast_stretch(rgb)
