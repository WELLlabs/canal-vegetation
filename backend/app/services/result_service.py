from __future__ import annotations

import json
from pathlib import Path

from app.core.config import get_settings
from app.models.database_models import Job
from app.models.db import SessionLocal


def load_result(job: Job) -> dict | None:
    if job.result_path and Path(job.result_path).is_file():
        return json.loads(Path(job.result_path).read_text(encoding="utf-8"))
    settings = get_settings()
    if job.project_id and job.prediction_id:
        fallback = Path(settings.project_root) / job.project_id / "predictions" / job.prediction_id / "result.json"
        if fallback.is_file():
            return json.loads(fallback.read_text(encoding="utf-8"))
    fallback = Path(settings.output_dir) / job.id / "result.json"
    if fallback.is_file():
        return json.loads(fallback.read_text(encoding="utf-8"))
    return None


def frontend_payload(job: Job) -> dict:
    data = load_result(job) or {}
    geojson = data.get("geojson") or {"type": "FeatureCollection", "features": []}
    if not geojson.get("features") and job.output_path:
        gj = Path(job.output_path) / "result.geojson"
        if gj.is_file():
            geojson = json.loads(gj.read_text(encoding="utf-8"))
    summary = data.get("summary") or {
        "total_reaches": len(geojson.get("features", [])),
        "clear": 0,
        "partial": 0,
        "moderate": 0,
        "full": 0,
        "damage": 0,
    }
    pred_id = job.prediction_id or data.get("prediction_id")
    return {
        "job_id": job.id,
        "prediction_id": pred_id,
        "project_id": job.project_id,
        "status": job.status,
        "pipeline_mode": data.get("pipeline_mode") or job.pipeline_mode,
        "model_version": data.get("model_version") or job.model_version,
        "label_source": data.get("label_source") or geojson.get("metadata", {}).get("label_source"),
        "summary": summary,
        "outputs": data.get("outputs") or {},
        "geojson": geojson,
        "features": geojson.get("features", []),
    }
