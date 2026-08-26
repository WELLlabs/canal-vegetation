from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from app.core.config import get_settings
from app.core.errors import MISSING_SHAPEFILE_SIDECARS, AppError
from app.pipeline.geospatial.alignment import validate_shapefile_sidecars
from app.schemas.job import JobStatus
from app.services.job_service import (
    create_job,
    enqueue_job,
    ensure_default_project,
    get_job_by_prediction,
    get_project,
)
from app.services.result_service import frontend_payload, load_result

router = APIRouter(tags=["predictions"])

ORTHO_OK = {".tif", ".tiff"}
ALIGN_OK = {".geojson", ".json", ".shp", ".shx", ".dbf", ".prj", ".cpg"}


def _save_upload(dest: Path, upload: UploadFile) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("wb") as f:
        shutil.copyfileobj(upload.file, f)
    return dest


@router.post("/projects/{project_id}/predictions", response_model=JobStatus)
async def create_prediction(
    project_id: str,
    ortho_file: UploadFile = File(...),
    alignment_file: UploadFile | None = File(None),
    alignment_files: list[UploadFile] = File(default=[]),
):
    """
    Start an async prediction.

    Ortho: GeoTIFF (.tif/.tiff).
    Alignment (optional): a .geojson, or a .shp **plus** sidecar uploads
    (.shx and .dbf required; .prj recommended) via repeated `alignment_files`.
    """
    project = get_project(project_id) or (ensure_default_project() if project_id == "default" else None)
    if project is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Project not found"})

    settings = get_settings()
    pred_id = str(uuid.uuid4())
    dest = Path(settings.upload_dir) / project_id / pred_id
    dest.mkdir(parents=True, exist_ok=True)

    suffix = Path(ortho_file.filename or "ortho.tif").suffix.lower()
    if suffix not in ORTHO_OK:
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_RASTER", "message": f"Orthomosaic must be GeoTIFF, got {suffix}"},
        )
    ortho_path = _save_upload(dest / f"orthophoto{suffix}", ortho_file)

    alignment_path = None
    extras = list(alignment_files or [])
    if alignment_file is not None and alignment_file.filename:
        extras = [alignment_file, *extras]
    if extras:
        alignment_path = _store_alignment(dest, extras)

    job = create_job(
        str(ortho_path.resolve()),
        alignment_path=str(Path(alignment_path).resolve()) if alignment_path else None,
        project_id=project_id,
        prediction_id=pred_id,
    )
    enqueue_job(job)
    return JobStatus(job_id=job.id, status="queued", progress=0, current_stage="queued", prediction_id=pred_id)


def _store_alignment(dest: Path, files: list[UploadFile]) -> str:
    saved: dict[str, Path] = {}
    for upload in files:
        name = Path(upload.filename or "alignment.bin").name
        ext = Path(name).suffix.lower()
        if ext not in ALIGN_OK:
            raise HTTPException(
                status_code=400,
                detail={"code": "INVALID_ALIGNMENT", "message": f"Unsupported alignment file: {name}"},
            )
        saved[ext] = _save_upload(dest / f"alignment{ext}", upload)

    if ".geojson" in saved or ".json" in saved:
        return str((saved.get(".geojson") or saved[".json"]).resolve())
    if ".shp" not in saved:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "INVALID_ALIGNMENT",
                "message": "Upload a .geojson or a .shp with .shx and .dbf sidecars.",
            },
        )
    try:
        validate_shapefile_sidecars(saved[".shp"])
    except AppError as exc:
        raise HTTPException(status_code=400, detail={"code": exc.code, "message": exc.message}) from exc
    return str(saved[".shp"].resolve())


@router.get("/predictions/{prediction_id}")
def get_prediction(prediction_id: str):
    job = get_job_by_prediction(prediction_id)
    if job is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Prediction not found"})
    if job.status != "completed":
        return JSONResponse(
            status_code=409 if job.status != "failed" else 409,
            content={
                "prediction_id": prediction_id,
                "job_id": job.id,
                "status": job.status,
                "progress": job.progress,
                "message": job.current_stage,
                "error": job.error_message,
                "code": job.error_code,
            },
        )
    return frontend_payload(job)


@router.get("/predictions/{prediction_id}/geojson")
def get_prediction_geojson(prediction_id: str):
    job = get_job_by_prediction(prediction_id)
    if job is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Prediction not found"})
    if job.status != "completed":
        raise HTTPException(status_code=409, detail={"code": "NOT_READY", "message": f"Job is {job.status}"})
    data = load_result(job) or {}
    geo = data.get("geojson")
    if not geo and job.output_path:
        gj = Path(job.output_path) / "result.geojson"
        if gj.is_file():
            geo = json.loads(gj.read_text(encoding="utf-8"))
    if not geo:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "GeoJSON not found"})
    return geo


@router.get("/predictions/{prediction_id}/images/{image_name}")
def get_prediction_image(prediction_id: str, image_name: str):
    job = get_job_by_prediction(prediction_id)
    if job is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Prediction not found"})
    settings = get_settings()
    root = (Path(settings.project_root) / (job.project_id or "default") / "predictions" / prediction_id / "images").resolve()
    target = (root / Path(image_name).name).resolve()
    if not str(target).startswith(str(root)) or not target.is_file():
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Image not found"})
    return FileResponse(target)


@router.get("/predictions/{prediction_id}/ortho")
def get_prediction_ortho(prediction_id: str):
    """Serve the downsampled RGB orthomosaic preview for the Leaflet overlay."""
    job = get_job_by_prediction(prediction_id)
    if job is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Prediction not found"})
    settings = get_settings()
    root = (Path(settings.project_root) / (job.project_id or "default") / "predictions" / prediction_id).resolve()
    target = (root / "ortho_preview.jpg").resolve()
    if not str(target).startswith(str(root)) or not target.is_file():
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Ortho preview not found"})
    return FileResponse(target, media_type="image/jpeg")
