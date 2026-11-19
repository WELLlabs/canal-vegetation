"""State / region canal centrelines.

Add a state to REGIONS, then drop its shapefile set into
``assets/regions/<folder>/``. When an orthophoto lands inside that layer's
extent, the app uses it as the canal centreline instead of the all-India layer.

Karnataka is first. Later states follow the same pattern.
"""
from __future__ import annotations
from pathlib import Path

from . import config

# key -> metadata. ``folder`` is under assets/regions/. The .shp basename can be
# anything; Canal.shp is preferred when several shapefiles are present.
REGIONS = {
    "karnataka": {
        "label": "Karnataka",
        "folder": "karnataka",
        "width": 6.0,
        "ctype": "main",
    },
}

_SIDECARS = (".shx", ".dbf", ".prj")
_BBOX_PAD_DEG = 0.1  # ~10 km, so images on the edge of the layer still match


def _folder(key: str) -> Path:
    return config.REGIONS_DIR / REGIONS[key]["folder"]


def shapefile_path(key: str) -> Path | None:
    """Return the region's .shp if the full shapefile set is present."""
    if key not in REGIONS:
        return None
    folder = _folder(key)
    if not folder.is_dir():
        return None
    preferred = folder / "Canal.shp"
    candidates = [preferred] if preferred.exists() else []
    candidates.extend(p for p in sorted(folder.glob("*.shp")) if p not in candidates)
    for shp in candidates:
        if all((shp.with_suffix(ext)).exists() for ext in _SIDECARS):
            return shp
    return None


def installed(key: str) -> bool:
    return shapefile_path(key) is not None


def _intersects(a, b) -> bool:
    return not (a[2] < b[0] or a[0] > b[2] or a[3] < b[1] or a[1] > b[3])


def _wgs84_bbox(shp_path: Path):
    """Shapefile extent in lon/lat, padded so edge orthophotos still match."""
    import shapefile
    from rasterio.crs import CRS
    from rasterio.warp import transform as warp_transform
    from .pipeline import geo

    sf = shapefile.Reader(str(shp_path))
    minx, miny, maxx, maxy = sf.bbox
    sf.close()
    xs = [minx, maxx, minx, maxx]
    ys = [miny, miny, maxy, maxy]
    crs = geo.read_prj_crs(shp_path)
    wgs = CRS.from_epsg(4326)
    if crs is not None and crs != wgs:
        xs, ys = warp_transform(crs, wgs, xs, ys)
    pad = _BBOX_PAD_DEG
    return [min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad]


def list_regions() -> list[dict]:
    out = []
    for key, spec in REGIONS.items():
        path = shapefile_path(key)
        item = {
            "key": key,
            "label": spec["label"],
            "folder": str(_folder(key).relative_to(config.APP_DIR)),
            "installed": path is not None,
            "shapefile": path.name if path else None,
        }
        out.append(item)
    return out


def pick_for_orthophoto(ortho_path) -> dict | None:
    """First installed region whose extent covers the orthophoto, else None."""
    from rasterio.crs import CRS
    from .pipeline import geo

    try:
        ortho_bbox = geo.footprint_bbox_in_crs(str(ortho_path), CRS.from_epsg(4326), pad_m=0)
    except Exception:
        return None
    for key, spec in REGIONS.items():
        path = shapefile_path(key)
        if path is None:
            continue
        try:
            layer_bbox = _wgs84_bbox(path)
        except Exception:
            continue
        if not _intersects(ortho_bbox, layer_bbox):
            continue
        return {
            "key": key,
            "path": path,
            "label": f"{spec['label']} canal centreline",
            "width": float(spec.get("width", 6.0)),
            "ctype": spec.get("ctype", ""),
        }
    return None
