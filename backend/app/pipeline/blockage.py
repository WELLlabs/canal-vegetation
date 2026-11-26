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


# ---------------------------------------------------------------------------------------------
# Vegetation-cover scoring: the core repo's method (canal-vegetation-model,
# pipeline/task2_blockage_percentage and bala_rewrite/production.py), which is also the
# client's field-verified convention (docs 08/09): blockage = share of the canal strip covered
# by vegetation, classed 0-5 / 6-40 / 41-70 / 71-100 per cent. The canal strip comes from the
# (refined) centreline, so no open-water model is needed. A dry, bare canal therefore reads
# "clear" instead of "blocked".
# ---------------------------------------------------------------------------------------------
VEG_THRESHOLDS = (5, 40, 70)

# Exactly the feature order the core repo's training.py / production.py fit and check.
FEATURE_NAMES = [
    'veg_frac', 'water_frac', 'bright_frac', 'soil_frac',
    'exg_mean', 'exg_std', 'sat_mean', 'val_mean',
    'gray_std', 'vari_mean',
    'veg_frac_core1', 'nonveg_frac_core1', 'water_frac_core1', 'veg_frac_core2',
    'veg_frac_delta',
    'edge_density', 'sobel_mean', 'hue_std',
]


def classify_veg_pct(pct: float, thr=VEG_THRESHOLDS) -> str:
    if pct <= thr[0]:
        return "clear"
    if pct <= thr[1]:
        return "partial"
    if pct <= thr[2]:
        return "moderate"
    return "blocked"


def to_4class(c3: str, pct: float) -> str:
    """Core repo's mapping of a 3-class model output (clear/partial/blocked) to 4 classes."""
    if c3 == "clear":
        return "clear"
    if c3 == "blocked":
        return "blocked"
    return "partial" if pct <= 30 else "moderate"


def feats(rgb, mk, mc1, mc2):
    """18 features, vendored unchanged from bala_rewrite/production.py feats()."""
    cp = mk > 0
    if cp.sum() < 15:
        return None
    r, g, b = [rgb[:, :, i].astype(np.float32) for i in range(3)]
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    h, s, v = [hsv[:, :, i].astype(np.float32) for i in range(3)]
    exg = 2 * g - r - b
    vari = (g - r) / (g + r - b + 1e-6)
    green = (h >= 35) & (h <= 85) & (s > 40) & (v > 50)
    veg = ((exg > 25) | ((vari > 0.1) & green))
    water = (v < 120) & (b > r) & (s > 15)
    bright = (v > 180)
    soil = (s < 60) & (v >= 120) & (v <= 200) & (r > g)
    gray = (0.299 * r + 0.587 * g + 0.114 * b).astype(np.uint8)
    edges = cv2.Canny(gray, 50, 150)
    sob = np.hypot(cv2.Sobel(gray.astype(np.float32), cv2.CV_32F, 1, 0, ksize=3),
                   cv2.Sobel(gray.astype(np.float32), cv2.CV_32F, 0, 1, ksize=3))
    fr = lambda c, m: float((c & (m > 0)).sum()) / max(1, int((m > 0).sum()))
    return [
        fr(veg, mk), fr(water, mk), fr(bright, mk), fr(soil, mk),
        float(exg[cp].mean()), float(exg[cp].std()), float(s[cp].mean()), float(v[cp].mean()),
        float(gray[cp].std()), float(vari[cp].mean()),
        fr(veg, mc1), fr(~veg, mc1), fr(water, mc1), fr(veg, mc2),
        fr(veg, mk) - fr(veg, mc1),
        float((edges[cp] > 0).mean()), float(sob[cp].mean()), float(h[cp].std())
    ]


def reach_vegetation(rgb_hwc_u8, corridor, line_px, px_m, classifier=None, thr=VEG_THRESHOLDS):
    """Score one reach by vegetation cover in its canal strip.

    corridor: strip mask (half width = 0.5 m + width/2, as in the core repo).
    line_px:  (N, 2) int32 (col, row) centreline inside the window, for the 1 m / 2 m core strips.
    classifier: optional core-repo bundle {'model', 'features', ...}; when given, its 3-class
    prediction (mapped with to_4class) sets the status and vegetation cover stays the blockage %.
    """
    cp = corridor > 0
    n = int(cp.sum())
    if n < 20:
        return {"status": "not_covered", "blockpct": None, "vegpct": None, "waterpct": None,
                "conf": None, "corridor_px": n}
    mc1 = np.zeros(corridor.shape, np.uint8)
    mc2 = np.zeros(corridor.shape, np.uint8)
    h1, h2 = max(1, int(1.0 / px_m)), max(1, int(2.0 / px_m))
    cv2.polylines(mc1, [line_px], False, 255, 2 * h1)
    cv2.polylines(mc2, [line_px], False, 255, 2 * h2)
    fv = feats(rgb_hwc_u8, corridor, mc1, mc2)
    if fv is None:
        return {"status": "not_covered", "blockpct": None, "vegpct": None, "waterpct": None,
                "conf": None, "corridor_px": n}
    vegpct = int(round(100 * fv[0]))
    out = {"blockpct": vegpct, "vegpct": vegpct, "waterpct": int(round(100 * fv[1])),
           "corridor_px": n, "method": "vegetation_cover", "conf": None}
    if classifier is not None:
        model = classifier["model"]
        x = np.asarray([fv], np.float64)
        c3 = str(model.predict(x)[0])
        out["model_class"] = c3
        out["status"] = to_4class(c3, vegpct)
        out["method"] = "classifier"
        if hasattr(model, "predict_proba"):
            try:
                pr = model.predict_proba(x)[0]
                out["conf"] = round(float(pr[list(model.classes_).index(c3)]), 3)
            except Exception:
                pass
    else:
        out["status"] = classify_veg_pct(vegpct, thr)
    return out
