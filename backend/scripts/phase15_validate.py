"""Phase 1.5: crop a real ATTANUR_4 window and run both pipeline modes.

This is real GeoTIFF pixels from the reference orthomosaic, not a synthetic raster.
Full-mosaic ATTANUR_4 is ~5085 tiles on CPU; the window is sized so the product
path can complete in this validation session.
"""
from __future__ import annotations

import json
import time
import traceback
from pathlib import Path

import numpy as np
import rasterio
from rasterio.windows import Window

from app.core.config import get_settings
from app.pipeline.geospatial.alignment import load_alignment
from app.pipeline.models.canal_model import CanalModel, get_device
from app.pipeline.run import run_prediction

ORTHO = Path(r"D:\Github\Canal Pipeline\TLBC_D95_ATTANUR_4_ortho.tif")
ALIGN = Path(r"D:\Github\Canal Pipeline\gis\TLBC_D95\TLBC_D95.shp")
OUT_DIR = Path(__file__).resolve().parents[1] / "data" / "validation"
WINDOW_SIZE = 4096


def crop_canal_window() -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    dest = OUT_DIR / "attanur4_real_window.tif"
    with rasterio.open(ORTHO) as src:
        col, row = src.width // 2, src.height // 2
        try:
            lines = load_alignment(ALIGN, src.crs)
            xs = np.concatenate([ln["pts_xy"][:, 0] for ln in lines])
            ys = np.concatenate([ln["pts_xy"][:, 1] for ln in lines])
            b = src.bounds
            ins = (xs >= b.left) & (xs <= b.right) & (ys >= b.bottom) & (ys <= b.top)
            if ins.any():
                rows, cols = rasterio.transform.rowcol(src.transform, xs[ins].tolist(), ys[ins].tolist())
                row = int(np.median(rows))
                col = int(np.median(cols))
        except Exception:
            traceback.print_exc()
        half = WINDOW_SIZE // 2
        r0 = max(0, row - half)
        c0 = max(0, col - half)
        r0 = min(r0, max(0, src.height - WINDOW_SIZE))
        c0 = min(c0, max(0, src.width - WINDOW_SIZE))
        h = min(WINDOW_SIZE, src.height - r0)
        w = min(WINDOW_SIZE, src.width - c0)
        data = src.read(window=Window(c0, r0, w, h))
        profile = src.profile.copy()
        profile.update(height=h, width=w, transform=src.window_transform(Window(c0, r0, w, h)))
        with rasterio.open(dest, "w", **profile) as dst:
            dst.write(data)
        meta = {
            "source": str(ORTHO),
            "window_row0": r0,
            "window_col0": c0,
            "width": w,
            "height": h,
            "count": src.count,
            "crs": str(src.crs),
            "pixel_size_m": abs(float(src.transform.a)),
        }
        (OUT_DIR / "window_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
        print("Wrote", dest, meta)
    return dest


def run_mode(ortho: Path, alignment: Path | None, prediction_id: str, model: CanalModel) -> dict:
    settings = get_settings()
    t0 = time.perf_counter()
    inf_t0 = None

    def progress(pct, stage):
        nonlocal inf_t0
        print(f"  [{pct:3d}] {stage}", flush=True)
        if inf_t0 is None and "inference" in stage.lower():
            inf_t0 = time.perf_counter()

    result = run_prediction(
        str(ortho),
        alignment_path=str(alignment) if alignment else None,
        project_id="phase15",
        prediction_id=prediction_id,
        settings=settings,
        canal_model=model,
        progress_cb=progress,
    )
    elapsed = time.perf_counter() - t0
    gj = json.loads(Path(result.geojson_path).read_text(encoding="utf-8"))
    thumbs = list((Path(result.thumbnail_directory)).glob("*.jpg"))
    return {
        "prediction_id": result.prediction_id,
        "pipeline_mode": result.pipeline_mode,
        "model_version": result.model_version,
        "label_source": result.label_source,
        "geojson_path": result.geojson_path,
        "n_features": len(gj.get("features", [])),
        "summary": result.summary,
        "n_thumbnails": len(thumbs),
        "job_seconds": round(elapsed, 1),
        "inference_marked_at_seconds": None if inf_t0 is None else round(inf_t0 - t0, 1),
        "statuses": {
            s: sum(1 for f in gj["features"] if f["properties"]["blockage_status"] == s)
            for s in ("clear", "partial", "moderate", "full")
        },
        "damage_true": sum(1 for f in gj["features"] if f["properties"]["structural_damage"]),
        "crs_sample": (gj["features"][0]["properties"]["centroid_lon"], gj["features"][0]["properties"]["centroid_lat"])
        if gj["features"]
        else None,
    }


def main():
    stats: dict = {"device": str(get_device()), "ortho_full": str(ORTHO), "alignment": str(ALIGN)}
    t_load = time.perf_counter()
    print("Loading model...", flush=True)
    model = CanalModel()
    stats["model_load_seconds"] = round(time.perf_counter() - t_load, 1)
    stats["model_version"] = model.model_version
    stats["weights_path"] = str(model.weights_path)
    print("Model", model.model_version, "on", stats["device"], flush=True)

    window = crop_canal_window()
    stats["window"] = json.loads((OUT_DIR / "window_meta.json").read_text(encoding="utf-8"))

    print("=== ortho_only ===", flush=True)
    stats["ortho_only"] = run_mode(window, None, "p15_ortho", model)
    print("=== ortho_plus_alignment ===", flush=True)
    stats["ortho_plus_alignment"] = run_mode(window, ALIGN, "p15_align", model)

    (OUT_DIR / "phase15_window_stats.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
