"""Per-reach silt estimate from DSM - DTM (matches the reference silt_calculator).

CHM = DSM - DTM is the height of material above bare ground. Inside a canal
corridor, positive CHM is treated as accumulated silt/sediment and classified:
  low   < 0.5 m
  medium 0.5-1.0 m
  high  >= 1.0 m
Volume is the depth integrated over the corridor area (sum of positive CHM x
pixel area), in cubic metres. This is an estimate: dense vegetation above the
channel also raises CHM, so figures read as indicative, not survey-grade."""
from __future__ import annotations
import numpy as np
import cv2
import rasterio
from rasterio.windows import Window, from_bounds
from rasterio.enums import Resampling

LOW = 0.5
HIGH = 1.0


def classify_depth(mean_depth: float) -> str:
    if mean_depth < LOW:
        return "low"
    if mean_depth < HIGH:
        return "medium"
    return "high"


def _nodata_to_nan(arr, src):
    a = arr.astype(np.float32)
    nod = src.nodata
    if nod is not None:
        a[a == nod] = np.nan
    a[a < -1e5] = np.nan
    return a


def reach_silt(dsm_src, dtm_src, pts_dsm, width: float) -> dict | None:
    """pts_dsm: reach vertices already in the DSM CRS. Returns silt metrics for
    the reach corridor, or None if the reach isn't covered by the elevation."""
    tr = dsm_src.transform
    H, W = dsm_src.height, dsm_src.width
    px_m = abs(tr.a)
    b = dsm_src.bounds

    xs = [p[0] for p in pts_dsm]; ys = [p[1] for p in pts_dsm]
    if (max(xs) < b.left or min(xs) > b.right or
            max(ys) < b.bottom or min(ys) > b.top):
        return None

    half = max(2, int((0.5 + width / 2) / px_m))
    margin = half + 8
    rows, cols = rasterio.transform.rowcol(tr, xs, ys)
    rows, cols = np.array(rows), np.array(cols)
    ins = (rows >= 0) & (rows < H) & (cols >= 0) & (cols < W)
    rows, cols = rows[ins], cols[ins]
    if len(rows) < 2:
        return None

    r0 = max(0, int(rows.min()) - margin); r1 = min(H, int(rows.max()) + margin)
    c0 = max(0, int(cols.min()) - margin); c1 = min(W, int(cols.max()) + margin)
    if r1 - r0 < 3 or c1 - c0 < 3:
        return None

    win = Window(c0, r0, c1 - c0, r1 - r0)
    dsm = _nodata_to_nan(dsm_src.read(1, window=win), dsm_src)

    # Read the DTM over the same world extent, resampled onto the DSM window grid.
    wleft, wtop = tr * (c0, r0)
    wright, wbottom = tr * (c1, r1)
    dtm_win = from_bounds(wleft, wbottom, wright, wtop, dtm_src.transform)
    dtm = _nodata_to_nan(
        dtm_src.read(1, window=dtm_win, out_shape=dsm.shape,
                     resampling=Resampling.bilinear), dtm_src)

    chm = np.where(np.isfinite(dsm) & np.isfinite(dtm), dsm - dtm, np.nan)

    corridor = np.zeros(dsm.shape, np.uint8)
    loc = np.array([[int(cols[k] - c0), int(rows[k] - r0)]
                    for k in range(len(rows))], np.int32)
    cv2.polylines(corridor, [loc], False, 255, max(2, 2 * half))
    cp = (corridor > 0) & np.isfinite(chm)
    if cp.sum() < 20:
        return None

    depths = chm[cp]
    pos = depths[depths > 0]
    px_area = px_m * px_m
    mean_depth = float(pos.mean()) if pos.size else 0.0
    volume = float(pos.sum()) * px_area if pos.size else 0.0
    low = int(((depths > 0) & (depths < LOW)).sum())
    med = int(((depths >= LOW) & (depths < HIGH)).sum())
    high = int((depths >= HIGH).sum())
    return {
        "silt_class": classify_depth(mean_depth) if pos.size else "low",
        "silt_mean_m": round(mean_depth, 3),
        "silt_vol_m3": round(volume, 1),
        "silt_area_m2": round(float(cp.sum()) * px_area, 1),
        "silt_px": {"low": low, "medium": med, "high": high},
    }
