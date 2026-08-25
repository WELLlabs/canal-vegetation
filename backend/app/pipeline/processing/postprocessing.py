from __future__ import annotations

import cv2
import numpy as np
from skimage.morphology import skeletonize

from app.core.config import Settings, get_settings
from app.pipeline.geospatial.corridor import apply_corridor_filter, build_corridor  # noqa: F401


def classify_canal_components(canal_raw: np.ndarray, px_m_ds: float, settings: Settings | None = None):
    """Notebook 07 Cell 6 — canal vs FIC-candidate vs rejected."""
    settings = settings or get_settings()
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    canal_clean = cv2.morphologyEx(canal_raw, cv2.MORPH_OPEN, kernel, iterations=1)
    canal_clean = cv2.morphologyEx(canal_clean, cv2.MORPH_CLOSE, kernel, iterations=2)

    n_labels, labels, stats, _ = cv2.connectedComponentsWithStats(canal_clean, connectivity=8)
    canal_only = np.zeros_like(canal_clean, dtype=np.uint8)
    fic_candidate = np.zeros_like(canal_clean, dtype=np.uint8)
    rejected = np.zeros_like(canal_clean, dtype=np.uint8)
    counts = {
        "canal": 0,
        "fic_candidate": 0,
        "small": 0,
        "compact": 0,
        "too_wide": 0,
        "fat_blob": 0,
    }

    for i in range(1, n_labels):
        area = int(stats[i, cv2.CC_STAT_AREA])
        x, y, w, h = [
            int(stats[i, k])
            for k in (
                cv2.CC_STAT_LEFT,
                cv2.CC_STAT_TOP,
                cv2.CC_STAT_WIDTH,
                cv2.CC_STAT_HEIGHT,
            )
        ]
        comp = (labels[y : y + h, x : x + w] == i).astype(np.uint8)
        full = labels == i

        if area < settings.min_component_area_px:
            rejected[full] = 1
            counts["small"] += 1
            continue

        aspect = max(w, h) / max(1, min(w, h))
        if aspect < settings.min_canal_aspect:
            rejected[full] = 1
            counts["compact"] += 1
            continue

        dt = cv2.distanceTransform(comp, cv2.DIST_L2, 5)
        width_vals = dt[comp > 0] * 2.0 * px_m_ds
        mean_width_m = float(np.mean(width_vals)) if width_vals.size else 0.0
        max_width_m = float(np.max(width_vals)) if width_vals.size else 0.0

        if max_width_m > settings.max_canal_width_m:
            rejected[full] = 1
            counts["too_wide"] += 1
            continue

        skel = skeletonize(comp > 0).astype(np.uint8)
        skel_ratio = float(skel.sum() / max(1, area))
        if skel_ratio < settings.min_skel_ratio:
            rejected[full] = 1
            counts["fat_blob"] += 1
            continue

        if (
            mean_width_m < settings.min_canal_mean_width_m
            or max_width_m < settings.min_canal_max_width_m
        ):
            fic_candidate[full] = 1
            counts["fic_candidate"] += 1
            continue

        canal_only[full] = 1
        counts["canal"] += 1

    return canal_only, fic_candidate, rejected, counts
