from __future__ import annotations

import cv2
import numpy as np
import rasterio
from rasterio.windows import Window
from rasterio.warp import transform as warp_xy
from rasterio.transform import xy as rxy

from app.core.config import Settings, get_settings


def veg_frac(rgb: np.ndarray, mask: np.ndarray) -> float | None:
    """predict_segments.py / line_blockage.py vegetation fraction."""
    cp = mask > 0
    if cp.sum() < 20:
        return None
    r, g, b = [rgb[:, :, i].astype(np.float32) for i in range(3)]
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    h, s, v = [hsv[:, :, i].astype(np.float32) for i in range(3)]
    exg = 2 * g - r - b
    vari = (g - r) / (g + r - b + 1e-6)
    green = (h >= 35) & (h <= 85) & (s > 40) & (v > 50)
    veg = ((exg > 25) | ((vari > 0.1) & green)) & cp
    n = max(1, int(cp.sum()))
    return float(veg.sum() / n)


def classify_blockage_pct(pct: float) -> str:
    """predict_segments.py 4-class bins."""
    if pct <= 5:
        return "clear"
    if pct <= 30:
        return "partial"
    if pct <= 80:
        return "moderate"
    return "full"


def measure_veg_rock(rgb: np.ndarray, mk: np.ndarray) -> tuple[float, float] | None:
    """detect_damage.py channel veg% and rocky fraction."""
    cp = mk > 0
    if cp.sum() < 15:
        return None
    r, g, b = [rgb[:, :, i].astype(np.float32) for i in range(3)]
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    h, s, v = [hsv[:, :, i].astype(np.float32) for i in range(3)]
    exg = 2 * g - r - b
    vari = (g - r) / (g + r - b + 1e-6)
    green = (h >= 35) & (h <= 85) & (s > 40) & (v > 50)
    gray = 0.299 * r + 0.587 * g + 0.114 * b
    g32 = gray.astype(np.float32)
    mean = cv2.boxFilter(g32, -1, (7, 7))
    sq = cv2.boxFilter(g32 * g32, -1, (7, 7))
    lstd = np.sqrt(np.maximum(sq - mean * mean, 0.0))
    greenish = (exg > 25) | ((vari > 0.1) & green)
    veg = greenish & (lstd > 14)
    water = (greenish & (lstd <= 14)) | ((v < 130) & (b > r) & (s > 15))
    base = ((exg < 12) & (v > 95) & (v < 235) & (s < 95) & (~water) & (~veg) & (lstd > 22)).astype(np.uint8)
    rocky = cv2.morphologyEx(base, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8)) > 0

    def fr(cond):
        return float((cond & (mk > 0)).sum()) / max(1, int((mk > 0).sum()))

    return fr(veg), fr(rocky)


def split_line_reaches(line: dict, reach_m: float) -> list[dict]:
    pts = line["pts_xy"]
    if len(pts) < 2:
        return []
    diffs = np.diff(pts, axis=0)
    seglen = np.hypot(diffs[:, 0], diffs[:, 1])
    chain = np.concatenate([[0.0], np.cumsum(seglen)])
    total = float(chain[-1])
    if total < 1e-3:
        return []
    starts = np.arange(0.0, total, reach_m) if total >= reach_m else np.array([0.0])
    base_ch = float(line["chainage_m"]) if line.get("chainage_m") is not None else 0.0
    out = []
    for i, s0 in enumerate(starts):
        s1 = min(s0 + reach_m, total)
        m = (chain >= s0) & (chain <= s1)
        sub = pts[m]
        if len(sub) < 2:
            i0 = int(np.searchsorted(chain, s0, side="left"))
            i1 = min(len(pts), int(np.searchsorted(chain, s1, side="right")) + 1)
            sub = pts[max(0, i0 - 1) : max(i0 + 1, i1)]
        if len(sub) < 2:
            continue
        rec = dict(line)
        rec["pts_xy"] = sub
        rec["reach_idx"] = i
        rec["chainage_m"] = float(base_ch + s0)
        rec["length_m"] = float(s1 - s0)
        out.append(rec)
    return out or [dict(line, reach_idx=0, chainage_m=base_ch, length_m=total)]


def analyze_alignment_reaches(orthophoto_path: str, lines: list[dict], settings: Settings | None = None) -> list[dict]:
    """
    Alignment-based blockage (predict_segments 4-class veg%) and
    structural damage (detect_damage rocky fraction).
    """
    settings = settings or get_settings()
    reach_m = settings.alignment_reach_m
    segments: list[dict] = []
    for line in lines:
        segments.extend(split_line_reaches(line, reach_m))

    rocks: list[float] = []
    with rasterio.open(orthophoto_path) as src:
        H, W = src.height, src.width
        tr = src.transform
        px_m = abs(float(tr.a))
        b = src.bounds
        for sg in segments:
            pts = sg["pts_xy"]
            cx, cy = float(pts[:, 0].mean()), float(pts[:, 1].mean())
            if not (b.left <= cx <= b.right and b.bottom <= cy <= b.top):
                sg["veg"] = None
                sg["rock"] = None
                continue
            hw = max(2, int((0.5 + sg["width_m"] / 2) / px_m))
            rr, cc = rasterio.transform.rowcol(tr, pts[:, 0].tolist(), pts[:, 1].tolist())
            rr, cc = np.array(rr), np.array(cc)
            ins = (rr >= 0) & (rr < H) & (cc >= 0) & (cc < W)
            rr, cc = rr[ins], cc[ins]
            if len(rr) < 2:
                sg["veg"] = None
                sg["rock"] = None
                continue
            r0 = max(0, int(rr.min()) - hw)
            r1 = min(H, int(rr.max()) + hw)
            a0 = max(0, int(cc.min()) - hw)
            a1 = min(W, int(cc.max()) + hw)
            if r1 - r0 < 4 or a1 - a0 < 4:
                sg["veg"] = None
                sg["rock"] = None
                continue
            d = src.read([1, 2, 3, 4] if src.count >= 4 else [1, 2, 3], window=Window(a0, r0, a1 - a0, r1 - r0))
            if src.count >= 4:
                valid = d[3] == 255
                rgb = np.transpose(d[:3], (1, 2, 0))
            else:
                rgb = np.transpose(d[:3], (1, 2, 0))
                valid = (rgb[:, :, 0].astype(np.float32) + rgb[:, :, 1] + rgb[:, :, 2]) >= 15
            loc = np.array([(int(cc[i] - a0), int(rr[i] - r0)) for i in range(len(rr))], np.int32)
            mk = np.zeros(rgb.shape[:2], np.uint8)
            cv2.polylines(mk, [loc], False, 255, 2 * hw)
            mk = ((mk > 0) & valid).astype(np.uint8)
            measured = measure_veg_rock(rgb.astype(np.uint8), mk)
            if measured is None:
                vf = veg_frac(rgb.astype(np.uint8), mk)
                sg["veg"] = vf
                sg["rock"] = 0.0
            else:
                sg["veg"], sg["rock"] = measured
            sg["bbox_px"] = (r0, a0, r1, a1)
            sg["loc_px"] = loc
            if sg["rock"] is not None:
                rocks.append(sg["rock"])

    rock_t = max(0.04, float(np.percentile(rocks, 95))) if rocks else 0.08
    reaches = []
    for sg in segments:
        if sg.get("bbox_px") is None:
            # predict_segments.py skips orthos whose bounds do not contain the segment.
            continue
        veg = sg.get("veg")
        pct = int(round((veg or 0.0) * 100)) if veg is not None else 0
        status = classify_blockage_pct(pct) if veg is not None else "clear"
        rock = sg.get("rock") or 0.0
        idx = len(reaches)
        reaches.append(
            {
                "reach_idx": idx,
                "global_reach_idx": idx,
                "canal_name": sg.get("canal_name") or "canal",
                "canal_type": sg.get("canal_type") or "distributary",
                "chainage_m": float(sg.get("chainage_m") or 0.0),
                "length_m": float(sg.get("length_m") or 0.0),
                "avg_width_m": float(sg.get("width_m") or 0.0),
                "status": status,
                "blockage_pct": pct,
                "structural_damage": bool(rock >= rock_t and veg is not None),
                "pts_xy": sg["pts_xy"],
                "bbox_px": sg.get("bbox_px"),
                "features": {"veg_frac": float(veg or 0.0), "rock_frac": float(rock)},
            }
        )
    return reaches


def alignment_box_lonlat(src, bbox_px: tuple[int, int, int, int] | None, pts_xy: np.ndarray) -> tuple[list, float, float]:
    """Polygon around the reach crop, WGS84, plus centroid."""
    tr = src.transform
    crs = src.crs
    if bbox_px is not None:
        r0, a0, r1, a1 = bbox_px
        rows = [r0, r0, r1, r1]
        cols = [a0, a1, a1, a0]
        xs, ys = rxy(tr, rows, cols)
        lons, lats = warp_xy(crs, "EPSG:4326", list(xs), list(ys))
        corners = [[float(a), float(b)] for a, b in zip(lons, lats)]
        cxs, cys = rxy(tr, [(r0 + r1) / 2], [(a0 + a1) / 2])
        clon, clat = warp_xy(crs, "EPSG:4326", list(cxs), list(cys))
        return corners, float(clon[0]), float(clat[0])
    xs, ys = pts_xy[:, 0].tolist(), pts_xy[:, 1].tolist()
    lons, lats = warp_xy(crs, "EPSG:4326", xs, ys)
    minx, maxx, miny, maxy = min(lons), max(lons), min(lats), max(lats)
    pad = 1e-5
    corners = [
        [minx - pad, maxy + pad],
        [maxx + pad, maxy + pad],
        [maxx + pad, miny - pad],
        [minx - pad, miny - pad],
    ]
    return corners, float(np.mean(lons)), float(np.mean(lats))
