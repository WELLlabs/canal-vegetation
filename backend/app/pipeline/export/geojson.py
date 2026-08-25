from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import rasterio
from rasterio.features import shapes
from rasterio.warp import transform as warp_xy
from rasterio.warp import transform_geom

from app.core.errors import CRS_ERROR, AppError
from app.schemas.prediction import canonical_blockage_status


def _geom_area(geom: dict) -> float:
    if geom.get("type") != "Polygon":
        return 0.0
    ring = geom["coordinates"][0]
    xs = [p[0] for p in ring]
    ys = [p[1] for p in ring]
    return abs(sum(xs[i] * ys[i + 1] - xs[i + 1] * ys[i] for i in range(len(xs) - 1))) / 2.0


def warp_geom_to_4326(geom: dict, src_crs) -> dict:
    if src_crs is None:
        return geom
    try:
        if str(src_crs).upper() in ("EPSG:4326", "OGC:CRS84"):
            return geom
        return transform_geom(src_crs, "EPSG:4326", geom, precision=8)
    except Exception as exc:
        raise AppError(CRS_ERROR, "Could not reproject geometry to EPSG:4326.") from exc


def centroid_lonlat(geom: dict) -> tuple[float, float]:
    coords = geom.get("coordinates") or []
    if geom.get("type") == "Polygon" and coords:
        ring = coords[0]
        xs = [p[0] for p in ring]
        ys = [p[1] for p in ring]
        return float(np.mean(xs[:-1] if len(xs) > 1 else xs)), float(np.mean(ys[:-1] if len(ys) > 1 else ys))
    return 0.0, 0.0


def _polygon_for_reach(labels_s: np.ndarray, reach: dict, transform, ds_a: int):
    rmin, cmin, rmax, cmax = reach["bbox_s"]
    cid = reach["canal_id"]
    region = (labels_s[rmin:rmax, cmin:cmax] == cid).astype(np.uint8)
    if region.sum() == 0:
        return None
    t = transform
    t_labels = rasterio.transform.Affine(t.a * ds_a, t.b, t.c, t.d, t.e * ds_a, t.f)
    window = rasterio.windows.Window(cmin, rmin, region.shape[1], region.shape[0])
    window_transform = rasterio.windows.transform(window, t_labels)
    geoms = list(shapes(region, mask=region > 0, transform=window_transform))
    if not geoms:
        return None
    geom, _ = max(geoms, key=lambda g: _geom_area(g[0]))
    return geom


def _bbox_polygon(reach: dict, transform) -> dict:
    rmin, cmin, rmax, cmax = reach["bbox"]
    xs = [cmin, cmax, cmax, cmin, cmin]
    ys = [rmin, rmin, rmax, rmax, rmin]
    coords = [rasterio.transform.xy(transform, y, x) for x, y in zip(xs, ys)]
    return {"type": "Polygon", "coordinates": [coords]}


def _feature(
    *,
    reach_id: str,
    geom: dict,
    tile_id: str,
    canal_name: str,
    canal_type: str,
    chainage_m: float,
    status: str,
    blockage_pct: int | float,
    structural_damage: bool,
    thumbnail_relpath: str,
    src_crs,
) -> dict:
    geom4326 = warp_geom_to_4326(geom, src_crs)
    lon, lat = centroid_lonlat(geom4326)
    return {
        "type": "Feature",
        "geometry": geom4326,
        "properties": {
            "reach_id": str(reach_id),
            "tile_id": tile_id,
            "canal_name": canal_name,
            "canal_type": canal_type,
            "chainage_m": float(chainage_m),
            "blockage_status": canonical_blockage_status(status),
            "blockage_pct": int(round(float(blockage_pct))),
            "structural_damage": bool(structural_damage),
            "centroid_lon": float(lon),
            "centroid_lat": float(lat),
            "thumbnail_relpath": thumbnail_relpath,
        },
    }


def canonical_collection(
    features: list[dict],
    *,
    project_id: str,
    prediction_id: str,
    model_version: str,
    pipeline_mode: str,
    label_source: str,
) -> dict:
    return {
        "type": "FeatureCollection",
        "metadata": {
            "project_id": project_id,
            "prediction_id": prediction_id,
            "model_version": model_version,
            "pipeline_mode": pipeline_mode,
            "label_source": label_source,
        },
        "features": features,
    }


def reaches_to_canonical_geojson(
    reaches: list[dict],
    labels_s: np.ndarray | None,
    canal_transform,
    ds_a: int,
    thumbnails: dict[str, str],
    *,
    src_crs,
    tile_id: str,
    project_id: str,
    prediction_id: str,
    model_version: str,
    pipeline_mode: str,
    label_source: str,
) -> dict:
    features = []
    for reach in reaches:
        rid = str(reach.get("global_reach_idx", reach.get("reach_idx", 0)))
        thumb = thumbnails.get(rid) or thumbnails.get(f"r{rid}") or ""
        if pipeline_mode == "ortho_plus_alignment" and reach.get("bbox_lonlat"):
            corners = reach["bbox_lonlat"]
            geom = {"type": "Polygon", "coordinates": [corners + [corners[0]]]}
            src_for_geom = None
        elif labels_s is not None and "bbox_s" in reach:
            geom = _polygon_for_reach(labels_s, reach, canal_transform, ds_a)
            if geom is None:
                geom = _bbox_polygon(reach, canal_transform)
            src_for_geom = src_crs
        else:
            geom = _bbox_polygon(reach, canal_transform)
            src_for_geom = src_crs

        pct = reach.get("blockage_pct")
        if pct is None:
            pct = reach.get("blockage_percentage", reach.get("blocked_fraction", 0) * 100)
        feats = reach.get("features") or {}
        if not pct and feats.get("veg_frac"):
            pct = feats["veg_frac"] * 100

        features.append(
            _feature(
                reach_id=rid,
                geom=geom,
                tile_id=tile_id,
                canal_name=str(reach.get("canal_name") or "predicted"),
                canal_type=str(reach.get("canal_type") or "unknown"),
                chainage_m=float(reach.get("chainage_m") or 0.0),
                status=str(reach.get("status") or "clear"),
                blockage_pct=pct or 0,
                structural_damage=bool(reach.get("structural_damage", reach.get("damage", False))),
                thumbnail_relpath=thumb if thumb.startswith("images/") else (f"images/{Path(thumb).name}" if thumb else ""),
                src_crs=src_for_geom,
            )
        )
    return canonical_collection(
        features,
        project_id=project_id,
        prediction_id=prediction_id,
        model_version=model_version,
        pipeline_mode=pipeline_mode,
        label_source=label_source,
    )


def write_geojson(path: str | Path, collection: dict) -> str:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(collection), encoding="utf-8")
    return str(path)
