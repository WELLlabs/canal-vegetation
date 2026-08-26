"""Downsampled RGB orthomosaic preview for the Leaflet imageOverlay."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import rasterio
from PIL import Image
from rasterio.enums import Resampling
from rasterio.warp import transform_bounds


def write_ortho_preview(
    orthophoto_path: str | Path,
    dest: str | Path,
    *,
    long_edge: int = 2048,
) -> dict:
    """
    Write a web-friendly JPEG preview and return placement metadata.

    Returns:
      {
        "path": str(dest),
        "ortho_bounds": [[south_lat, west_lon], [north_lat, east_lon]],  # EPSG:4326
        "width": int,
        "height": int,
      }
    """
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    long_edge = max(256, int(long_edge))

    with rasterio.open(orthophoto_path) as src:
        h, w = src.height, src.width
        scale = long_edge / float(max(h, w))
        out_h = max(1, int(round(h * scale)))
        out_w = max(1, int(round(w * scale)))

        bands = [1, 2, 3]
        if src.count < 3:
            raise ValueError(f"Ortho needs at least 3 bands, got {src.count}")
        data = src.read(
            bands,
            out_shape=(3, out_h, out_w),
            resampling=Resampling.bilinear,
        )
        rgb = np.transpose(data, (1, 2, 0)).astype(np.float32)
        rgb = _stretch(rgb)
        Image.fromarray(rgb).save(dest, format="JPEG", quality=85, optimize=True)

        west, south, east, north = _bounds_wgs84(src)
        ortho_bounds = [[south, west], [north, east]]

    return {
        "path": str(dest.resolve()),
        "ortho_bounds": ortho_bounds,
        "width": out_w,
        "height": out_h,
    }


def _bounds_wgs84(src) -> tuple[float, float, float, float]:
    """Return (west, south, east, north) in EPSG:4326."""
    left, bottom, right, top = src.bounds
    if src.crs is None:
        return float(left), float(bottom), float(right), float(top)
    crs_str = str(src.crs).upper()
    if crs_str in ("EPSG:4326", "OGC:CRS84"):
        # Geographic: x=lon, y=lat
        return float(left), float(bottom), float(right), float(top)
    west, south, east, north = transform_bounds(src.crs, "EPSG:4326", left, bottom, right, top, densify_pts=21)
    return float(west), float(south), float(east), float(north)


def _stretch(rgb: np.ndarray) -> np.ndarray:
    out = np.empty_like(rgb, dtype=np.uint8)
    for ch in range(3):
        band = rgb[:, :, ch]
        lo, hi = np.percentile(band, [2, 98])
        if hi <= lo:
            out[:, :, ch] = np.clip(band, 0, 255).astype(np.uint8)
        else:
            out[:, :, ch] = np.clip((band - lo) / (hi - lo) * 255.0, 0, 255).astype(np.uint8)
    return out
