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
import json, zipfile, tempfile
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


def _utm_for(lon: float, lat: float) -> CRS:
    """Metric UTM CRS for a lon/lat, so lengths can be measured in metres."""
    zone = int((lon + 180) // 6) + 1
    return CRS.from_epsg((32600 if lat >= 0 else 32700) + zone)


def _cut_line_metric(pts, src_crs, base_chainage, reach_m=REACH_M):
    """Cut a raw centreline into ``reach_m`` reaches, measuring length in METRES
    even when ``src_crs`` is geographic (degrees). Reaches are returned in the
    source CRS so downstream reprojection to the orthophoto CRS is unchanged."""
    if src_crs is not None and getattr(src_crs, "is_geographic", False):
        lon = sum(p[0] for p in pts) / len(pts)
        lat = sum(p[1] for p in pts) / len(pts)
        mcrs = _utm_for(lon, lat)
        mx, my = warp_transform(src_crs, mcrs, [p[0] for p in pts],
                                [p[1] for p in pts])
        chunks, after = _cut_centreline(list(zip(mx, my)), base_chainage, reach_m)
        out = []
        for ch, cpts in chunks:
            bx, by = warp_transform(mcrs, src_crs, [p[0] for p in cpts],
                                    [p[1] for p in cpts])
            out.append((ch, list(zip(bx, by))))
        return out, after
    return _cut_centreline(pts, base_chainage, reach_m)


def footprint_bbox_in_crs(ortho_path, target_crs: CRS, pad_m: float = 200.0):
    """Bounding box of an orthophoto's footprint, reprojected into ``target_crs``
    and padded, as [minx, miny, maxx, maxy]. Used to pull only the local canal(s)
    out of a large national layer. ``pad_m`` is in metres and converted to the
    target units when the target CRS is geographic."""
    with rasterio.open(ortho_path) as src:
        b = src.bounds
        ocrs = src.crs
    xs = [b.left, b.right, b.left, b.right]
    ys = [b.bottom, b.bottom, b.top, b.top]
    if ocrs is not None and target_crs is not None and ocrs != target_crs:
        xs, ys = warp_transform(ocrs, target_crs, xs, ys)
    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)
    pad = pad_m
    if target_crs is not None and getattr(target_crs, "is_geographic", False):
        pad = pad_m / 111320.0             # ~metres to degrees
    return [minx - pad, miny - pad, maxx + pad, maxy + pad]


def _in_bbox(pts, bbox):
    """True if any point falls inside bbox [minx, miny, maxx, maxy]."""
    for x, y in pts:
        if bbox[0] <= x <= bbox[2] and bbox[1] <= y <= bbox[3]:
            return True
    return False


def load_reaches(shp_path: Path, default_width: float = 6.0,
                 default_ctype: str = "", reach_m: float = REACH_M,
                 bbox=None) -> tuple[list[dict], CRS | None]:
    """Return [{id, canal, ctype, width, chainage, pts:[(x,y)...]}], source CRS.

    Shapefiles that already carry a ``chainage`` field are read reach-by-reach
    (unchanged behaviour). Shapefiles without one are treated as raw centrelines
    and cut into ``reach_m`` reaches, so a single traced canal line still yields
    a full chain of scored reaches.

    ``bbox`` (in the shapefile's own CRS) restricts the read to features near
    that box and keeps only reaches touching it. This is what makes a huge
    national canal layer usable: only the canal(s) under the orthophoto are
    read and cut, not the whole country."""
    src_crs = read_prj_crs(shp_path)
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

    # pyshp 2.3+ can spatially pre-filter by bbox using the shape index (fast).
    try:
        records = sf.shapeRecords(bbox=bbox) if bbox else sf.shapeRecords()
    except TypeError:
        records = sf.shapeRecords()        # older pyshp: filter below by hand

    for sr in records:
        rec = dict(zip(flds, sr.record))
        pts = [(float(x), float(y)) for x, y in sr.shape.points]
        if len(pts) < 2:
            continue
        canal = field(rec, "canal", "canname", "name", default="")
        ctype = field(rec, "ctype", "can_type", "type", default=default_ctype)
        width = float(field(rec, "width", default=default_width) or default_width)

        if pre_cut:
            if bbox and not _in_bbox(pts, bbox):
                continue
            rid += 1
            out.append({
                "id": int(field(rec, "id", default=rid) or rid),
                "canal": canal, "ctype": ctype, "width": width,
                "chainage": float(field(rec, "chainage", default=0) or 0),
                "pts": pts,
            })
        else:
            chunks, running = _cut_line_metric(pts, src_crs, running, reach_m)
            for ch, cpts in chunks:
                if bbox and not _in_bbox(cpts, bbox):
                    continue
                rid += 1
                out.append({
                    "id": rid, "canal": canal, "ctype": ctype, "width": width,
                    "chainage": round(ch, 1), "pts": cpts,
                })

    sf.close()
    return out, src_crs


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


# ---------------------------------------------------------------------------
# Optional user-supplied alignment (override): a canal line the user uploads for
# their own orthophoto, instead of the bundled national layer. Accepts a zipped
# shapefile set or a GeoJSON of LineString / MultiLineString. Georeferencing
# still comes from the orthophoto's own CRS.
# ---------------------------------------------------------------------------

def _geojson_crs(gj) -> CRS:
    crs = gj.get("crs")
    if isinstance(crs, dict):
        name = (crs.get("properties") or {}).get("name", "")
        try:
            if name:
                return CRS.from_user_input(name)
        except Exception:
            pass
    return CRS.from_epsg(4326)


def _iter_lines(geom):
    if not geom:
        return
    t = geom.get("type")
    c = geom.get("coordinates")
    if t == "LineString":
        yield [(float(p[0]), float(p[1])) for p in c if len(p) >= 2]
    elif t == "MultiLineString":
        for ln in c:
            yield [(float(p[0]), float(p[1])) for p in ln if len(p) >= 2]
    elif t == "GeometryCollection":
        for g in geom.get("geometries", []):
            yield from _iter_lines(g)


def load_geojson_reaches(path: Path, default_width: float = 6.0,
                         default_ctype: str = "", reach_m: float = REACH_M
                         ) -> tuple[list[dict], CRS | None]:
    gj = json.loads(Path(path).read_text())
    src_crs = _geojson_crs(gj)
    feats = gj.get("features") if gj.get("type") == "FeatureCollection" \
        else [gj] if gj.get("type") == "Feature" \
        else [{"type": "Feature", "geometry": gj, "properties": {}}]
    out: list[dict] = []
    running = 0.0
    rid = 0
    for ft in feats:
        props = {str(k).lower(): v for k, v in (ft.get("properties") or {}).items()}
        canal = props.get("canal") or props.get("canname") or props.get("name") or ""
        ctype = props.get("ctype") or props.get("can_type") or default_ctype
        try:
            width = float(props.get("width") or default_width)
        except (TypeError, ValueError):
            width = default_width
        for pts in _iter_lines(ft.get("geometry")):
            if len(pts) < 2:
                continue
            if "chainage" in props:
                rid += 1
                out.append({"id": rid, "canal": canal, "ctype": ctype,
                            "width": width,
                            "chainage": float(props.get("chainage") or 0),
                            "pts": pts})
            else:
                chunks, running = _cut_line_metric(pts, src_crs, running, reach_m)
                for ch, cpts in chunks:
                    rid += 1
                    out.append({"id": rid, "canal": canal, "ctype": ctype,
                                "width": width, "chainage": round(ch, 1),
                                "pts": cpts})
    return out, src_crs


def _shp_from_zip(zip_path: Path) -> Path:
    dest = Path(tempfile.mkdtemp(prefix="align_"))
    with zipfile.ZipFile(zip_path) as z:
        z.extractall(dest)
    shps = list(dest.rglob("*.shp"))
    if not shps:
        raise ValueError("Zip has no .shp file. Include the shapefile set "
                         "(.shp, .shx, .dbf and ideally .prj).")
    return shps[0]


def load_reaches_any(path: Path, default_width: float = 6.0,
                     default_ctype: str = "", reach_m: float = REACH_M,
                     bbox=None) -> tuple[list[dict], CRS | None]:
    """Load reaches from a bundled or uploaded .shp, a zipped shapefile set, or a
    GeoJSON. ``bbox`` (shapefile CRS) restricts a shapefile read to a local area,
    used to clip the national layer to the orthophoto footprint."""
    p = Path(path)
    suf = p.suffix.lower()
    if suf == ".zip":
        return load_reaches(_shp_from_zip(p), default_width, default_ctype,
                            reach_m, bbox=bbox)
    if suf in (".geojson", ".json"):
        return load_geojson_reaches(p, default_width, default_ctype, reach_m)
    return load_reaches(p, default_width, default_ctype, reach_m, bbox=bbox)
