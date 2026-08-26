from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path
from typing import Callable

import rasterio

from app.core.config import Settings, get_settings
from app.core.errors import PREDICTION_FAILED, AppError
from app.pipeline.detection.alignment_analysis import (
    alignment_box_lonlat,
    analyze_alignment_reaches,
)
from app.pipeline.detection.blockage_detection import detect_blockages
from app.pipeline.detection.canal_detection import detect_canals
from app.pipeline.export.geojson import reaches_to_canonical_geojson, write_geojson
from app.pipeline.export.geotiff import write_uint8_geotiff
from app.pipeline.export.ortho_preview import write_ortho_preview
from app.pipeline.export.thumbnails import write_reach_thumbnails
from app.pipeline.geospatial.alignment import load_alignment
from app.pipeline.models.canal_model import CanalModel
from app.pipeline.models.registry import get_canal_model
from app.schemas.prediction import PredictionResult, canonical_blockage_status

logger = logging.getLogger(__name__)
ProgressFn = Callable[[int, str], None]


def _pred_dir(settings: Settings, project_id: str, prediction_id: str) -> Path:
    root = Path(settings.project_root) / project_id / "predictions" / prediction_id
    (root / "images").mkdir(parents=True, exist_ok=True)
    return root


def run_prediction(
    ortho_path: str,
    alignment_path: str | None = None,
    project_id: str | None = None,
    prediction_id: str | None = None,
    job_id: str | None = None,
    settings: Settings | None = None,
    progress_cb: ProgressFn | None = None,
    canal_model: CanalModel | None = None,
) -> PredictionResult:
    settings = settings or get_settings()
    project_id = project_id or "default"
    prediction_id = prediction_id or str(uuid.uuid4())
    pipeline_mode = "ortho_plus_alignment" if alignment_path else "ortho_only"
    out_dir = _pred_dir(settings, project_id, prediction_id)
    tile_id = Path(ortho_path).stem

    def progress(pct: int, stage: str) -> None:
        logger.info("prediction=%s stage=%s progress=%s", prediction_id, stage, pct)
        if progress_cb:
            progress_cb(pct, stage)

    try:
        progress(5, "Loading canal model")
        model = canal_model or get_canal_model()
        model_version = model.model_version

        alignment_lines = None
        if alignment_path:
            progress(8, "Reading alignment")
            with rasterio.open(ortho_path) as src:
                dst_crs = src.crs
            alignment_lines = load_alignment(alignment_path, dst_crs)

        progress(12, "Running canal inference")
        canal_data = detect_canals(
            ortho_path,
            model=model,
            settings=settings,
            alignment_path=alignment_path,
            alignment_lines=alignment_lines,
            progress_cb=progress,
        )
        write_uint8_geotiff(
            out_dir / "canal_mask.tif",
            canal_data["binary"],
            canal_data["geo"]["crs"],
            canal_data["geo"]["transform"],
            tags={"NOTE": "canal-only mask; FIC candidates excluded"},
        )

        labels_s = None
        ds_a = settings.analysis_downscale
        if pipeline_mode == "ortho_plus_alignment":
            progress(50, "Alignment blockage and damage")
            reaches = analyze_alignment_reaches(ortho_path, alignment_lines or [], settings)
            with rasterio.open(ortho_path) as src:
                for r in reaches:
                    corners, lon, lat = alignment_box_lonlat(src, r.get("bbox_px"), r["pts_xy"])
                    r["bbox_lonlat"] = corners
                    r["centroid_lon"] = lon
                    r["centroid_lat"] = lat
            label_source = "rule"
        else:
            progress(45, "Reach extraction and blockage scoring")
            pack = detect_blockages(ortho_path, canal_data, settings)
            reaches = pack["reaches"]
            labels_s = pack["labels_s"]
            ds_a = pack["ds_a"]
            label_source = "model"

        progress(80, "Writing thumbnails and GeoJSON")
        thumbs = write_reach_thumbnails(
            ortho_path,
            reaches,
            labels_s,
            settings.downscale_factor,
            out_dir / "images",
        )
        progress(88, "Writing ortho preview")
        preview_meta = write_ortho_preview(ortho_path, out_dir / "ortho_preview.jpg")
        collection = reaches_to_canonical_geojson(
            reaches,
            labels_s,
            canal_data["geo"]["transform"],
            ds_a,
            thumbs,
            src_crs=canal_data["geo"]["crs"],
            tile_id=tile_id,
            project_id=project_id,
            prediction_id=prediction_id,
            model_version=model_version,
            pipeline_mode=pipeline_mode,
            label_source=label_source,
            ortho_bounds=preview_meta["ortho_bounds"],
        )
        geojson_path = write_geojson(out_dir / "result.geojson", collection)
        summary = _summary(collection["features"])
        metadata = {
            "project_id": project_id,
            "prediction_id": prediction_id,
            "job_id": job_id,
            "pipeline_mode": pipeline_mode,
            "model_version": model_version,
            "label_source": label_source,
            "summary": summary,
            "ortho_bounds": preview_meta["ortho_bounds"],
        }
        metadata_path = out_dir / "metadata.json"
        metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

        result = PredictionResult(
            prediction_id=prediction_id,
            project_id=project_id,
            pipeline_mode=pipeline_mode,
            model_version=model_version,
            label_source=label_source,
            geojson_path=geojson_path,
            thumbnail_directory=str(out_dir / "images"),
            metadata_path=str(metadata_path),
            job_id=job_id,
            summary=summary,
            geojson=collection,
            outputs={
                "geojson": geojson_path,
                "thumbnails": str(out_dir / "images"),
                "canal_mask": str(out_dir / "canal_mask.tif"),
                "ortho_preview": str(out_dir / "ortho_preview.jpg"),
            },
        )
        (out_dir / "result.json").write_text(result.model_dump_json(), encoding="utf-8")
        progress(100, "completed")
        return result
    except AppError:
        raise
    except Exception as exc:
        logger.exception("Prediction failed for %s", prediction_id)
        raise AppError(PREDICTION_FAILED, "Prediction failed. See server logs for details.", status_code=500) from exc


def _summary(features: list[dict]) -> dict:
    statuses = [f.get("properties", {}).get("blockage_status") for f in features]
    return {
        "total_reaches": len(features),
        "clear": sum(1 for s in statuses if s == "clear"),
        "partial": sum(1 for s in statuses if s == "partial"),
        "moderate": sum(1 for s in statuses if s == "moderate"),
        "full": sum(1 for s in statuses if s == "full"),
        "damage": sum(1 for f in features if f.get("properties", {}).get("structural_damage")),
    }


# kept for older blockage raster helpers
def map_status_for_raster(status: str) -> int:
    canon = canonical_blockage_status(status)
    return {"clear": 1, "partial": 2, "moderate": 3, "full": 4}.get(canon, 0)
