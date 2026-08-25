from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from rasterio.crs import CRS
from rasterio.warp import transform as warp_xy

from app.core.errors import (
    CRS_ERROR,
    INVALID_ALIGNMENT,
    MISSING_SHAPEFILE_SIDECARS,
    AppError,
)

REQUIRED_SHAPEFILE_SIDECARS = (".shx", ".dbf")


def validate_shapefile_sidecars(shp_path: str | Path) -> None:
    path = Path(shp_path)
    missing = [ext for ext in REQUIRED_SHAPEFILE_SIDECARS if not path.with_suffix(ext).is_file()]
    if missing:
        raise AppError(
            MISSING_SHAPEFILE_SIDECARS,
            f"Incomplete shapefile upload. Missing sidecar(s): {', '.join(missing)}. "
            "A .shp must be accompanied by .shx and .dbf (and .prj when the file is not lon/lat).",
        )


def _looks_lonlat(xs: list[float], ys: list[float]) -> bool:
    if not xs:
        return False
    return max(abs(x) for x in xs) <= 180.5 and max(abs(y) for y in ys) <= 90.5


def _crs_from_prj(prj_path: Path) -> CRS | None:
    if not prj_path.is_file():
        return None
    text = prj_path.read_text(encoding="utf-8", errors="ignore").strip()
    if not text:
        return None
    try:
        return CRS.from_wkt(text)
    except Exception:
        try:
            return CRS.from_string(text)
        except Exception as exc:
            raise AppError(CRS_ERROR, f"Could not parse {prj_path.name}: {exc}") from exc


def _reproject_xy(xs: list[float], ys: list[float], src_crs: CRS, dst_crs: CRS) -> np.ndarray:
    if src_crs == dst_crs:
        return np.column_stack([xs, ys])
    try:
        ox, oy = warp_xy(src_crs, dst_crs, xs, ys)
    except Exception as exc:
        raise AppError(CRS_ERROR, f"Failed to reproject alignment to raster CRS: {exc}") from exc
    return np.column_stack([ox, oy])


def _line_from_props(props: dict, pts: np.ndarray) -> dict:
    name = str(props.get("canal") or props.get("name") or props.get("Name") or props.get("canal_name") or "")
    ctype = str(props.get("type") or props.get("ctype") or props.get("canal_type") or "").strip().lower()
    if not ctype:
        n = name.lower()
        if "lateral" in n:
            ctype = "lateral"
        elif "tlbc" in n or "main" in n or "canal" in n:
            ctype = "main"
        else:
            ctype = "distributary"
    width = props.get("width")
    try:
        width_m = float(width) if width not in (None, "") else None
    except (TypeError, ValueError):
        width_m = None
    if width_m is None:
        width_m = 14.0 if ctype == "main" else 5.0 if ctype == "distributary" else 3.3
    chainage = props.get("chainage") if props.get("chainage") is not None else props.get("chainage_m")
    try:
        chainage_m = float(chainage) if chainage not in (None, "") else None
    except (TypeError, ValueError):
        chainage_m = None
    return {
        "canal_name": name or "canal",
        "canal_type": ctype,
        "width_m": float(width_m),
        "chainage_m": chainage_m,
        "pts_xy": pts,
    }


def _coords_to_lines(coords) -> list[list[list[float]]]:
    if not coords:
        return []
    first = coords[0]
    if isinstance(first, (int, float)):
        return [coords]
    if first and isinstance(first[0], (int, float)):
        return [coords]
    out = []
    for part in coords:
        out.extend(_coords_to_lines(part))
    return out


def load_alignment(path: str | Path, dst_crs) -> list[dict]:
    """Load polyline alignment and reproject vertices into the orthomosaic CRS."""
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix in {".geojson", ".json"}:
        return _load_geojson(path, dst_crs)
    if suffix == ".shp":
        validate_shapefile_sidecars(path)
        return _load_shapefile(path, dst_crs)
    raise AppError(INVALID_ALIGNMENT, f"Unsupported alignment type '{suffix}'. Use .geojson or .shp")


def _load_geojson(path: Path, dst_crs) -> list[dict]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise AppError(INVALID_ALIGNMENT, f"Invalid GeoJSON: {exc}") from exc
    features = data.get("features") if data.get("type") == "FeatureCollection" else [data]
    if not features:
        raise AppError(INVALID_ALIGNMENT, "Alignment GeoJSON has no features")
    src_crs = CRS.from_epsg(4326)
    crs_name = (data.get("crs") or {}).get("properties", {}).get("name")
    if crs_name:
        try:
            src_crs = CRS.from_user_input(crs_name)
        except Exception:
            src_crs = CRS.from_epsg(4326)
    lines = []
    for feat in features:
        if not feat:
            continue
        geom = feat.get("geometry") or {}
        gtype = geom.get("type")
        coords = geom.get("coordinates")
        if gtype not in ("LineString", "MultiLineString") or not coords:
            continue
        for part in _coords_to_lines(coords):
            xs = [float(p[0]) for p in part]
            ys = [float(p[1]) for p in part]
            if len(xs) < 2:
                continue
            pts = _reproject_xy(xs, ys, src_crs, CRS.from_user_input(dst_crs))
            lines.append(_line_from_props(feat.get("properties") or {}, pts))
    if not lines:
        raise AppError(INVALID_ALIGNMENT, "Alignment GeoJSON must contain LineString or MultiLineString features")
    return lines


def _load_shapefile(path: Path, dst_crs) -> list[dict]:
    try:
        import shapefile
    except ImportError as exc:
        raise AppError(INVALID_ALIGNMENT, "pyshp is required to read shapefiles. Install pyshp.") from exc
    reader = shapefile.Reader(str(path))
    fields = [f[0] for f in reader.fields[1:]]
    src_crs = _crs_from_prj(path.with_suffix(".prj"))
    lines = []
    for sr in reader.shapeRecords():
        if sr.shape.shapeType not in (shapefile.POLYLINE, shapefile.POLYLINEZ, shapefile.POLYLINEM, 3, 13, 23):
            pts_raw = sr.shape.points
            if len(pts_raw) < 2:
                continue
        else:
            pts_raw = sr.shape.points
        if len(pts_raw) < 2:
            continue
        xs = [float(p[0]) for p in pts_raw]
        ys = [float(p[1]) for p in pts_raw]
        if src_crs is None:
            if _looks_lonlat(xs, ys):
                src_crs = CRS.from_epsg(4326)
            else:
                raise AppError(
                    CRS_ERROR,
                    "Shapefile has no .prj and coordinates are not lon/lat. Provide a .prj sidecar.",
                )
        pts = _reproject_xy(xs, ys, src_crs, CRS.from_user_input(dst_crs))
        props = dict(zip(fields, sr.record)) if fields else {}
        lines.append(_line_from_props(props, pts))
    reader.close()
    if not lines:
        raise AppError(INVALID_ALIGNMENT, "Shapefile contains no polyline vertices")
    return lines
