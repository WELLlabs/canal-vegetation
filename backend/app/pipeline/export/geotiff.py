from __future__ import annotations

from pathlib import Path

import numpy as np
import rasterio


def write_uint8_geotiff(path: str | Path, array: np.ndarray, crs, transform, tags: dict | None = None):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=array.shape[0],
        width=array.shape[1],
        count=1,
        dtype="uint8",
        crs=crs,
        transform=transform,
        compress="lzw",
    ) as dst:
        dst.write(array.astype(np.uint8), 1)
        if tags:
            dst.update_tags(**{k: str(v) for k, v in tags.items()})
    return str(path)


def write_float_geotiff(path: str | Path, array: np.ndarray, crs, transform, nodata=-9999.0):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=array.shape[0],
        width=array.shape[1],
        count=1,
        dtype="float32",
        crs=crs,
        transform=transform,
        compress="lzw",
        nodata=nodata,
    ) as dst:
        dst.write(array.astype(np.float32), 1)
    return str(path)
