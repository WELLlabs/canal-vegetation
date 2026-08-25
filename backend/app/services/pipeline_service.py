from __future__ import annotations

from typing import Callable

from app.core.config import Settings, get_settings
from app.pipeline.run import run_prediction
from app.schemas.prediction import PredictionResult

ProgressFn = Callable[[int, str], None]


def run_pipeline(
    job_id: str,
    orthophoto_path: str,
    dsm_path: str | None = None,
    dtm_path: str | None = None,
    alignment_path: str | None = None,
    project_id: str | None = None,
    prediction_id: str | None = None,
    config: Settings | None = None,
    progress_cb: ProgressFn | None = None,
) -> dict:
    """Phase 1 entry: DSM/DTM ignored. FIC UNet and silt are not run."""
    del dsm_path, dtm_path
    settings = config or get_settings()
    result: PredictionResult = run_prediction(
        ortho_path=orthophoto_path,
        alignment_path=alignment_path,
        project_id=project_id,
        prediction_id=prediction_id or job_id,
        job_id=job_id,
        settings=settings,
        progress_cb=progress_cb,
    )
    payload = result.model_dump()
    payload["job_id"] = job_id
    payload["status"] = "completed"
    payload["features"] = payload.get("geojson", {}).get("features", [])
    return payload
