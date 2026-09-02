"""Geospatial helpers: read bundled reaches, reproject coordinates, and map
world coordinates to raster pixels. Kept dependency-light (pyshp + rasterio)."""
from __future__ import annotations
from pathlib import Path
import numpy as np
import shapefile  # pyshp
import rasterio
from rasterio.warp import transform as warp_transform
from rasterio.crs import CRS


def read_prj_crs(shp_path: Path):
    prj = Path(str(shp_path).replace(".shp", ".prj"))
    if prj.exists():
        try:
            return CRS.from_wkt(prj.read_text().strip())
        except Exception:
            pass
    return None


def load_reaches(shp_path: Path) -> tuple[list[dict], CRS | None]:
    """Return [{id, canal, ctype, width, chainage, pts:[(x,y)...]}], source CRS."""
    sf = shapefile.Reader(str(shp_path))
    flds = [f[0] for f in sf.fields[1:]]
    out = []
    for sr in sf.shapeRecords():
        rec = dict(zip(flds, sr.record))
        pts = [(float(x), float(y)) for x, y in sr.shape.points]
        if len(pts) < 2:
            continue
        out.append({
            "id": int(rec.get("id") or (len(out) + 1)),
            "canal": rec.get("canal") or "",
            "ctype": rec.get("ctype") or "",
            "width": float(rec.get("width") or 6),
            "chainage": float(rec.get("chainage") or 0),
            "pts": pts,
        })
    sf.close()
    return out, read_prj_crs(shp_path)


def reproject_pts(pts, src_crs, dst_crs):
    """Reproject a list of (x,y) from src_crs to dst_crs. No-op if either is None
    or they are equal."""
    if src_crs is None or dst_crs is None or src_crs == dst_crs:
        return pts
    xs, ys = zip(*pts)
    nx, ny = warp_transform(src_crs, dst_crs, list(xs), list(ys))
    return list(zip(nx, ny))


def to_lonlat(pts, src_crs):
    if src_crs is None:
        return pts
    xs, ys = zip(*pts)
    lon, lat = warp_transform(src_crs, CRS.from_epsg(4326), list(xs), list(ys))
    return list(zip(lon, lat))


def centroid(pts):
    a = np.asarray(pts, float)
    return float(a[:, 0].mean()), float(a[:, 1].mean())
