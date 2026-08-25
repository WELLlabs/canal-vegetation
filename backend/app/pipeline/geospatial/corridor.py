from __future__ import annotations

import cv2
import numpy as np
import rasterio

from app.core.errors import CRS_ERROR, AppError
from app.pipeline.geospatial.alignment import load_alignment


def apply_corridor_filter(canal_only: np.ndarray, corridor: np.ndarray | None) -> np.ndarray:
    if corridor is None or corridor.sum() == 0:
        return canal_only
    return (canal_only * corridor).astype(np.uint8)


def build_corridor_from_lines(
    fpath: str,
    shape_ds: tuple[int, int],
    ds: int,
    lines: list[dict],
    buf_m: float,
) -> np.ndarray:
    """Notebook 07 corridor: buffer polylines (already in raster CRS) onto the DS mask grid."""
    h_ds, w_ds = shape_ds
    with rasterio.open(fpath) as src:
        tr = src.transform
        px_m = abs(float(tr.a))
    corr = np.zeros((h_ds, w_ds), np.uint8)
    buf_px = max(3, int(buf_m / (px_m * ds)))
    for line in lines:
        pts = line["pts_xy"]
        rows, cols = rasterio.transform.rowcol(tr, pts[:, 0].tolist(), pts[:, 1].tolist())
        loc = [(int(c / ds), int(r / ds)) for r, c in zip(rows, cols)]
        loc = [
            (x, y)
            for x, y in loc
            if -buf_px <= x < w_ds + buf_px and -buf_px <= y < h_ds + buf_px
        ]
        if len(loc) > 1:
            cv2.polylines(corr, [np.array(loc, np.int32)], False, 1, 2 * buf_px)
    return corr


def build_corridor(
    fpath: str,
    shape_ds: tuple[int, int],
    ds: int,
    shapefile_path: str,
    buf_m: float,
):
    """Notebook 07: traced-line corridor. `shapefile_path` may be .shp or .geojson."""
    if not shapefile_path:
        return None
    from pathlib import Path

    if not Path(shapefile_path).exists():
        return None
    with rasterio.open(fpath) as src:
        crs = src.crs
    try:
        lines = load_alignment(shapefile_path, crs)
    except AppError:
        raise
    except Exception as exc:
        raise AppError(CRS_ERROR, f"Failed to build corridor: {exc}") from exc
    return build_corridor_from_lines(fpath, shape_ds, ds, lines, buf_m)
