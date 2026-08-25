from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np
from skimage.morphology import skeletonize
from skimage.measure import label, regionprops

from app.pipeline.processing.preprocessing import CLASS_BG, linearity_filter, vari


@dataclass(frozen=True)
class TileOffset:
    col: int
    row: int


def iter_blocks(width: int, height: int, patch_size: int = 512, stride: int = 256):
    """Notebook 04 tiling grid."""
    cols = list(range(0, width - patch_size + 1, stride))
    rows = list(range(0, height - patch_size + 1, stride))
    for row in rows:
        for col in cols:
            yield TileOffset(col=col, row=row)


def make_mask(r, g, b, alpha, px_m):
    """
    Notebook 04_patch_tiling make_mask.
    Returns uint8 mask: 0=bg 1=main 2=lateral 3=distrib 4=FIC 5=bund
    """
    valid = alpha > 128
    bright = (r + g + b) / 3.0
    grey = np.abs(r - g) + np.abs(g - b)
    vi = vari(r, g, b)

    main_min = int(8.0 / px_m)
    lat_min = int(3.0 / px_m)
    fic_min = max(2, int(0.15 / px_m))
    fic_max = int(0.5 / px_m)
    conn_px = max(5, int(3.0 / px_m))

    k3 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    k5 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))

    c_raw = (valid & (vi < 0.06) & (bright > 120) & (grey < 25)).astype(np.uint8)
    c_raw = cv2.morphologyEx(c_raw, cv2.MORPH_OPEN, k3)
    c_raw = cv2.morphologyEx(c_raw, cv2.MORPH_CLOSE, k5)
    concrete = linearity_filter(
        c_raw.astype(bool), min_aspect=2.5, max_blob_area=int((3.0 / px_m) ** 2)
    )
    c_dist = cv2.distanceTransform(concrete.astype(np.uint8) * 255, cv2.DIST_L2, 5) * 2
    c_skel = skeletonize(concrete)

    mask = np.zeros(r.shape, dtype=np.uint8)
    c_labels = label(concrete, connectivity=2)
    for region in regionprops(c_labels):
        comp = c_labels == region.label
        sp = comp & c_skel
        med = float(np.median(c_dist[sp])) if sp.any() else 0
        if med >= main_min:
            mask[comp] = 1
        elif med >= lat_min:
            mask[comp] = 2
        else:
            mask[comp] = 3

    e_raw = (
        valid
        & (vi < 0.09)
        & (bright > 65)
        & (bright < 215)
        & (r > b + 3)
        & (grey >= 10)
        & ~concrete
    ).astype(np.uint8)
    e_raw = cv2.morphologyEx(e_raw, cv2.MORPH_OPEN, k3)
    e_raw = cv2.morphologyEx(e_raw, cv2.MORPH_CLOSE, k3)
    earthen = linearity_filter(
        e_raw.astype(bool), min_aspect=2.5, max_blob_area=int((2.0 / px_m) ** 2)
    )
    e_dist = cv2.distanceTransform(earthen.astype(np.uint8) * 255, cv2.DIST_L2, 5) * 2
    e_skel = skeletonize(earthen)

    ck = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (conn_px * 2 + 1, conn_px * 2 + 1))
    c_dil = cv2.dilate(concrete.astype(np.uint8), ck).astype(bool)
    e_labels = label(earthen, connectivity=2)
    for region in regionprops(e_labels):
        comp = e_labels == region.label
        sp = comp & e_skel
        if not sp.any():
            mask[comp] = 5
            continue
        med = float(np.median(e_dist[sp]))
        touches = bool((comp & c_dil).any())
        mask[comp] = 4 if (touches and fic_min <= med <= fic_max) else 5

    mask[~valid] = CLASS_BG
    return mask
