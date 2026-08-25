from __future__ import annotations

import numpy as np
from skimage.measure import label, regionprops

CLASS_BG = 0


def vari(r, g, b):
    d = g.astype(float) + r.astype(float) - b.astype(float)
    d = np.where(np.abs(d) < 1e-6, 1e-6, d)
    return np.clip((g.astype(float) - r.astype(float)) / d, -1, 1)


def linearity_filter(mask, min_aspect=2.5, max_blob_area=None):
    labeled = label(mask, connectivity=2)
    filtered = np.zeros_like(mask, dtype=bool)
    for region in regionprops(labeled):
        if region.area < 8:
            continue
        minor = region.minor_axis_length
        aspect = (
            (region.major_axis_length / minor)
            if minor > 1e-3
            else region.major_axis_length
        )
        if aspect >= min_aspect or (max_blob_area and region.area <= max_blob_area):
            filtered[labeled == region.label] = True
    return filtered


def contrast_stretch(rgb: np.ndarray, valid_mask: np.ndarray | None = None, lo=2, hi=98):
    """Notebook contrast_stretch / contrast_stretch_b4."""
    out = np.zeros_like(rgb, dtype=np.uint8)
    if rgb.ndim != 3:
        return out
    if valid_mask is None:
        valid_mask = rgb.sum(axis=2) > 0
    for c in range(min(3, rgb.shape[2])):
        ch = rgb[:, :, c].astype(np.float64)
        vpx = ch[valid_mask]
        if vpx.size < 100:
            v = ch[ch > 0]
            if v.size == 0:
                continue
            pl, ph = np.percentile(v, [lo, hi])
        else:
            pl, ph = np.percentile(vpx, [lo, hi])
        if ph - pl < 5:
            continue
        s = np.clip((ch - pl) / (ph - pl) * 255, 0, 255).astype(np.uint8)
        s[~valid_mask] = 0
        out[:, :, c] = s
    return out


def imagenet_normalize(rgb_chw: np.ndarray, mean, std) -> np.ndarray:
    x = rgb_chw.astype(np.float32) / 255.0
    for i in range(3):
        x[i] = (x[i] - mean[i]) / std[i]
    return x
