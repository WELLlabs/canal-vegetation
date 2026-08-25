from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator

import numpy as np
import rasterio
from rasterio.windows import Window


@dataclass(frozen=True)
class RasterMeta:
    path: str
    width: int
    height: int
    count: int
    crs: object
    transform: object
    nodata: float | None
    pixel_size_m: float


def open_meta(path: str) -> RasterMeta:
    try:
        src_ctx = rasterio.open(path)
    except Exception as exc:
        from app.core.errors import INVALID_RASTER, AppError

        raise AppError(INVALID_RASTER, f"Could not open raster: {exc}") from exc
    with src_ctx as src:
        if src.count < 3:
            from app.core.errors import UNSUPPORTED_BAND_CONFIGURATION, AppError

            raise AppError(
                UNSUPPORTED_BAND_CONFIGURATION,
                f"Raster has {src.count} band(s); RGB or RGBA (3+ bands) is required.",
            )
        px = abs(float(src.transform.a))
        return RasterMeta(
            path=path,
            width=src.width,
            height=src.height,
            count=src.count,
            crs=src.crs,
            transform=src.transform,
            nodata=src.nodata,
            pixel_size_m=px,
        )


def read_window_rgba(
    src: rasterio.DatasetReader,
    col: int,
    row: int,
    width: int,
    height: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Read RGB + valid mask from a window. Never reads the full raster."""
    w = min(width, src.width - col)
    h = min(height, src.height - row)
    if w <= 0 or h <= 0:
        rgb = np.zeros((3, height, width), dtype=np.float32)
        valid = np.zeros((height, width), dtype=bool)
        return rgb, valid

    if src.count >= 4:
        data = src.read([1, 2, 3, 4], window=Window(col, row, w, h))
        rgb = data[:3].astype(np.float32)
        valid = data[3] == 255
    else:
        data = src.read([1, 2, 3], window=Window(col, row, w, h))
        rgb = data.astype(np.float32)
        valid = (rgb[0] + rgb[1] + rgb[2]) >= 15

    if h != height or w != width:
        padded_rgb = np.zeros((3, height, width), dtype=np.float32)
        padded_valid = np.zeros((height, width), dtype=bool)
        padded_rgb[:, :h, :w] = rgb
        padded_valid[:h, :w] = valid
        return padded_rgb, padded_valid
    return rgb, valid


def iter_tile_offsets(width: int, height: int, tile: int, step: int) -> Iterator[tuple[int, int]]:
    """Same grid as notebooks: range(0, dim - tile + 1, step)."""
    if width < tile or height < tile:
        yield 0, 0
        return
    for row in range(0, height - tile + 1, step):
        for col in range(0, width - tile + 1, step):
            yield col, row
