"""Geospatial helpers: read bundled reaches, reproject coordinates, and map
world coordinates to raster pixels. Kept dependency-light (pyshp + rasterio).

A canal alignment can arrive in two shapes:
  * pre-cut reaches  — many short LineString features that already carry a
    ``chainage`` field (the bundled TLBC / NRBC segments). Used as-is.
  * a raw centreline — one (or a few) long LineString(s) with no ``chainage``
    field (e.g. a canal traced in QGIS). It is densified and cut into fixed
    ``reach_m`` reaches here, with chainage measured along the line.
"""
from __future__ import annotations
from pathlib import Path
import numpy as np
import shapefile  # pyshp
import rasterio
from rasterio.warp import transform as warp_transform
from rasterio.crs import CRS

from .. import config

REACH_M = float(getattr(config, "REACH_LENGTH_M", 50))
SAMPLE_M = 2.0


def read_prj_crs(shp_path: Path):
    prj = Path(str(shp_path).replace(".shp", ".prj"))
    if prj.exists():
        try:
            return CRS.from_wkt(prj.read_text().strip())
        except Exception:
            pass
    return None


def _densify(pts, step=SAMPLE_M):
    """Resample an ordered polyline to ~step spacing. Returns (samples Nx2,
    chainage N) in the same CRS/units as the input."""
    a = np.asarray(pts, float)
    if len(a) < 2:
        return a, np.zeros(len(a))
    seg = np.hypot(np.diff(a[:, 0]), np.diff(a[:, 1]))
    chain = np.concatenate([[0.0], np.cumsum(seg)])
    total = float(chain[-1])
    if total <= 0:
        return a, np.zeros(len(a))
    sc = np.arange(0.0, total, step)
    sx = np.interp(sc, chain, a[:, 0])
    sy = np.interp(sc, chain, a[:, 1])
    return np.column_stack([sx, sy]), sc


def _cut_centreline(pts, base_chainage, reach_m=REACH_M):
    """Cut one long polyline into consecutive reach_m reaches.
    Returns (list of (chainage, [(x,y)...]), chainage after this feature)."""
    samp, sc = _densify(pts)
    total = float(sc[-1]) if len(sc) else 0.0
    out = []
    c0 = 0.0
    while c0 < total:
        m = (sc >= c0) & (sc < c0 + reach_m)
        pr = samp[m]
        if len(pr) >= 2:
            out.append((base_chainage + c0,
                        [(float(x), float(y)) for x, y in pr]))
        c0 += reach_m
    return out, base_chainage + total


def load_reaches(shp_path: Path, default_width: float = 6.0,
                 default_ctype: str = "", reach_m: float = REACH_M
                 ) -> tuple[list[dict], CRS | None]:
    """Return [{id, canal, ctype, width, chainage, pts:[(x,y)...]}], source CRS.

    Shapefiles that already carry a ``chainage`` field are read reach-by-reach
    (unchanged behaviour). Shapefiles without one are treated as raw centrelines
    and cut into ``reach_m`` reaches, so a single traced canal line still yields
    a full chain of scored reaches."""
    sf = shapefile.Reader(str(shp_path))
    flds = [f[0] for f in sf.fields[1:]]
    lower = {f.lower(): f for f in flds}

    def field(rec, *names, default=None):
        for n in names:
            key = lower.get(n)
            if key is not None:
                v = rec.get(key)
                if v not in (None, ""):
                    return v
        return default

    pre_cut = "chainage" in lower          # decided once per shapefile
    out: list[dict] = []
    running = 0.0                          # cumulative chainage for raw lines
    rid = 0

    for sr in sf.shapeRecords():
        rec = dict(zip(flds, sr.record))
        pts = [(float(x), float(y)) for x, y in sr.shape.points]
        if len(pts) < 2:
            continue
        canal = field(rec, "canal", "canname", "name", default="")
        ctype = field(rec, "ctype", "can_type", "type", default=default_ctype)
        width = float(field(rec, "width", default=default_width) or default_width)

        if pre_cut:
            rid += 1
            out.append({
                "id": int(field(rec, "id", default=rid) or rid),
                "canal": canal, "ctype": ctype, "width": width,
                "chainage": float(field(rec, "chainage", default=0) or 0),
                "pts": pts,
            })
        else:
            chunks, running = _cut_centreline(pts, running, reach_m)
            for ch, cpts in chunks:
                rid += 1
                out.append({
                    "id": rid, "canal": canal, "ctype": ctype, "width": width,
                    "chainage": round(ch, 1), "pts": cpts,
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
