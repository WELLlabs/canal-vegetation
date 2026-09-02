"""Turn a canal-segmentation probability map into a per-reach blockage class.

Interpretation: the fixed model segments the OPEN canal channel. Within a reach
corridor, the fraction the model still sees as open channel = open_frac.
blockage% = 100 * (1 - open_frac). Vegetation fraction is computed as a
supporting signal (a blocked channel is usually vegetation-choked)."""
from __future__ import annotations
import numpy as np
import cv2

# 4-class thresholds on blockage percentage (from reference pipeline).
def classify_pct(pct: float) -> str:
    if pct <= 5:
        return "clear"
    if pct <= 30:
        return "partial"
    if pct <= 80:
        return "moderate"
    return "blocked"


def veg_fraction(rgb_hwc_u8: np.ndarray, corridor: np.ndarray) -> float:
    """Green-vegetation fraction inside the corridor (ExG + VARI, as reference)."""
    cp = corridor > 0
    if cp.sum() < 20:
        return 0.0
    r, g, b = (rgb_hwc_u8[:, :, i].astype(np.float32) for i in range(3))
    hsv = cv2.cvtColor(rgb_hwc_u8, cv2.COLOR_RGB2HSV)
    h, s, v = (hsv[:, :, i].astype(np.float32) for i in range(3))
    exg = 2 * g - r - b
    vari = (g - r) / (g + r - b + 1e-6)
    green = (h >= 35) & (h <= 85) & (s > 40) & (v > 50)
    veg = ((exg > 25) | ((vari > 0.1) & green)) & cp
    return float(veg.sum() / max(1, int(cp.sum())))


def reach_blockage(canal_prob: np.ndarray, corridor: np.ndarray,
                   rgb_hwc_u8: np.ndarray, thr: float = 0.4) -> dict:
    """Compute blockage metrics for one reach corridor."""
    cp = corridor > 0
    n = int(cp.sum())
    if n < 20:
        return {"status": "not_covered", "blockpct": None, "openpct": None,
                "vegpct": None, "conf": None, "corridor_px": n}
    canal_mask = canal_prob >= thr
    open_frac = float(canal_mask[cp].mean())          # channel still open
    conf = float(canal_prob[cp].mean())               # mean model confidence
    veg = veg_fraction(rgb_hwc_u8, corridor)
    blockpct = int(round(100 * (1 - open_frac)))
    return {
        "status": classify_pct(blockpct),
        "blockpct": blockpct,
        "openpct": int(round(100 * open_frac)),
        "vegpct": int(round(100 * veg)),
        "conf": round(conf, 3),
        "corridor_px": n,
    }
