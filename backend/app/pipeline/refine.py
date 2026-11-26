"""Move the canal alignment onto the canal visible in the orthophoto, before scoring.

Why: blockage is scored in a narrow strip (the reach width, about 5-7 m) around the alignment.
The national canal layer (and some bundled lines) can sit tens of metres off the real canal,
so the strip lands on fields or tree lines and every reach reads "blocked". Widening the strip
does not fix that: it adds field pixels and pushes blockage further up. Instead this step SEARCHES
a wide band (search_m, default 80 m) around the alignment with the line-detection model trained
in the Colab notebook, traces the canal inside it, and hands the corrected centreline to the
scorer, which keeps scoring the narrow strip, now on the canal.

Uses the same code as the notebook (linetrace.py is a copy of canal_extract_light.py) and the
model it trains (<work_dir>/model.pt), installed as config/models/canal_lines.pt.
If that file is missing, the step is skipped and the original alignment is used.
"""
from __future__ import annotations
from pathlib import Path
import time

from .. import config


def model_path() -> Path:
    return config.MODELS_DIR / config.LINE_MODEL_FILE


def available() -> bool:
    return config.REFINE_ENABLED and model_path().exists()


def _read_lines(align_path: Path, bbox_clip: bool, crs, bounds):
    from . import linetrace as lt
    import geopandas as gpd
    p = Path(align_path)
    if bbox_clip:
        return lt.load_national(p, crs, bounds)
    if p.suffix.lower() == ".zip":
        from .geo import _shp_from_zip
        p = _shp_from_zip(p)
    g = gpd.read_file(p)
    if g.crs is None:                     # GeoJSON without CRS is WGS84 by definition
        g = g.set_crs("EPSG:4326")
    return lt.load_canals(g, crs, bounds)


def refine_alignment(ortho_path, align_path, bbox_clip: bool, out_dir, progress=None):
    """Returns (path to refined shapefile or None, line probability GeoTIFF or None, info dict)."""
    if not available():
        return None, None, {"refined": False,
                      "note": f"line model {config.LINE_MODEL_FILE} not installed; original alignment used"}
    from . import linetrace as lt
    t0 = time.time()
    P = {**lt.DEFAULTS, **config.REFINE_PARAMS}
    if P["retry_corridor_m"] and P["retry_corridor_m"] > P["buffer_m"]:
        P["retry_corridor_m"] = P["buffer_m"]
    model, MD = lt.load_model(model_path())
    if progress:
        progress(6, "Reading orthophoto for canal search")
    img, tr, crs, bounds, res = lt.load_small(ortho_path, MD["res_m"])
    g = _read_lines(Path(align_path), bbox_clip, crs, bounds)
    if g.empty:
        return None, None, {"refined": False, "note": "no alignment lines under this orthophoto"}
    if progress:
        progress(8, f"Searching {P['buffer_m']:.0f} m either side of {len(g)} canal line(s)")
    out, out_r, prob, _ = lt.refine_lines(img, tr, crs, res, g, model, MD, P, lt.scale_of(ortho_path),
                                       progress=lambda m: progress and progress(14, "Tracing canal centreline"))
    del img
    n_in = int(len(out))
    all_lines, all_reaches = out, out_r
    out, out_r, dropped = _keep_visible_canals(out, out_r, P)
    out_dir = Path(out_dir) / "refined"
    out_dir.mkdir(parents=True, exist_ok=True)
    _write_map_lines(g, all_lines, out, out_dir / "lines_map.geojson")
    import rasterio
    prob_path = out_dir / "line_prob.tif"
    with rasterio.open(prob_path, "w", driver="GTiff", height=prob.shape[0], width=prob.shape[1], count=1,
                       dtype="uint8", crs=crs, transform=tr, compress="lzw", tiled=True) as dst:
        dst.write(prob, 1)
    if all_lines is not None and len(all_lines):
        all_lines.to_file(out_dir / "refined_lines.geojson", driver="GeoJSON")
    if all_reaches is not None and len(all_reaches):
        all_reaches.to_file(out_dir / "refined_reaches.geojson", driver="GeoJSON")
    dropped_names = [d["name"] for d in dropped[:8]]
    extra = f"; skipped {len(dropped)} mapped line(s) with no visible canal" + (
        f" ({', '.join(dropped_names)})" if dropped_names else "")
    thresholds = {k: P[k] for k in ("min_mean_prob", "min_coverage", "pixel_prob_threshold")}
    if not len(out):
        return None, prob_path, {
            "refined": True, "no_visible_canal": True, "search_m": P["buffer_m"],
            "lines": 0, "lines_in": n_in, "dropped_lines": dropped, "thresholds": thresholds,
            "seconds": round(time.time() - t0),
            "note": (f"none of the {n_in} mapped line(s) under this orthophoto look like a canal "
                     f"in the imagery{extra}."),
        }
    shp = out_dir / "alignment.shp"
    keep = [c for c in out.columns
            if c not in ("line_id", "mean_prob", "coverage", "accepted", "corr_m", "n_reach", "n_check")]
    out[keep].to_file(shp)
    info = {
        "refined": True,
        "search_m": P["buffer_m"],
        "lines": int(len(out)),
        "lines_in": n_in,
        "dropped_lines": dropped,
        "thresholds": thresholds,
        "mean_shift_m": round(float(out["shift_m"].mean()), 1),
        "max_shift_m": round(float(out["shift_m"].max()), 1),
        "low_confidence_reaches": int((out_r["status"] == "check").sum()) if len(out_r) else 0,
        "seconds": round(time.time() - t0),
        "note": ("alignment moved onto the canal detected in the orthophoto"
                 f"{extra}."),
    }
    return shp, prob_path, info


def _keep_visible_canals(out, out_r, P):
    """Drop whole shapefile lines that are not a supported canal in the imagery.

    The Karnataka layer includes laterals, minors and village traces. Per-reach scoring can
    still mark a road as blocked if the tracer snaps onto it, so a line is scored only if the
    line model supports it along its trace (same rule as the Karnataka notebook): mean
    probability >= min_mean_prob AND coverage (share of traced pixels >= pixel_prob_threshold)
    >= min_coverage. Lines whose reaches are all flagged 'check' are dropped as well.
    Rejected lines are reported (and drawn on the map) but never become scored reaches.
    """
    if out is None or not len(out):
        return out, out_r, []
    mp = out["mean_prob"].fillna(0)
    cov = out["coverage"].fillna(0) if "coverage" in out.columns else mp * 0 + 1
    low_prob = mp < float(P["min_mean_prob"])
    low_cov = cov < float(P["min_coverage"])
    all_chk = out["line_id"] < -1                          # all False
    if out_r is not None and len(out_r) and "line_id" in out_r.columns:
        n_tot = out_r.groupby("line_id").size()
        n_chk = out_r.loc[out_r["status"] == "check"].groupby("line_id").size()
        frac_chk = n_chk.reindex(n_tot.index).fillna(0) / n_tot.replace(0, 1)
        all_chk = out["line_id"].isin(frac_chk[frac_chk >= 0.99].index)
    keep = ~(low_prob | low_cov | all_chk)
    out = out.copy()
    out["accepted"] = keep
    dropped = []
    for i, row in out.loc[~keep].iterrows():
        why = [w for w, f in (("low mean probability", low_prob[i]), ("low coverage", low_cov[i]),
                              ("no confident reach", all_chk[i])) if f]
        ctype = row.get("can_type")
        dropped.append({
            "name": str(row.get("canname") or row.get("name") or f"line {row.get('line_id')}"),
            "mean_prob": round(float(row.get("mean_prob") or 0), 3),
            "coverage": round(float(row.get("coverage") or 0), 3),
            "reason": ", ".join(why),
            "can_type": None if ctype is None else str(ctype),
        })
    kept = out.loc[keep].copy()
    if out_r is None:
        kept_r = out_r
    elif not len(kept):
        kept_r = out_r.iloc[0:0].copy()
    else:
        kept_r = out_r.loc[out_r["line_id"].isin(set(kept["line_id"]))].copy()
    return kept, kept_r, dropped


def _write_map_lines(ref, traced_all, kept, path):
    """One WGS84 GeoJSON for the results map: the Karnataka reference lines under the image
    (role=reference), accepted traced lines (role=accepted) and rejected ones (role=rejected)."""
    import json
    import geopandas as gpd
    import pandas as pd
    parts = []
    if ref is not None and len(ref):
        r = gpd.GeoDataFrame(geometry=ref.geometry.values, crs=ref.crs)
        r["role"] = "reference"
        parts.append(r)
    if traced_all is not None and len(traced_all):
        ok = set(kept["line_id"]) if kept is not None and len(kept) else set()
        t = traced_all.copy()
        col = "canname" if "canname" in t.columns else ("name" if "name" in t.columns else None)
        names = [None if v is None or pd.isna(v) else str(v) for v in (t[col] if col else [None] * len(t))]
        t = gpd.GeoDataFrame({
            "role": ["accepted" if k in ok else "rejected" for k in t["line_id"]],
            "name": names,
            "mean_prob": t["mean_prob"].astype(float).round(3),
            "coverage": t["coverage"].astype(float).round(3) if "coverage" in t.columns else None,
            "shift_m": t["shift_m"].astype(float).round(1),
        }, geometry=t.geometry.values, crs=t.crs)
        parts.append(t)
    if not parts:
        gj = {"type": "FeatureCollection", "features": []}
        Path(path).write_text(json.dumps(gj))
        return
    allg = pd.concat([p.to_crs("EPSG:4326") for p in parts], ignore_index=True)
    allg = gpd.GeoDataFrame(allg, geometry="geometry", crs="EPSG:4326").explode(index_parts=False)
    allg = allg[allg.geom_type == "LineString"]
    Path(path).write_text(allg.to_json(drop_id=True))
