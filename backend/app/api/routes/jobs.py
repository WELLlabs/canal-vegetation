from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.pipeline.io.storage import get_storage
from app.schemas.job import JobCreate, JobStatus
from app.services.job_service import create_job, enqueue_job, ensure_default_project, get_job

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("", response_model=JobStatus)
def create_processing_job(body: JobCreate):
    storage = get_storage()
    if not storage.exists(body.orthophoto_path):
        raise HTTPException(status_code=400, detail={"code": "INVALID_RASTER", "message": "orthophoto_path does not exist"})
    ensure_default_project()
    job = create_job(body.orthophoto_path, body.dsm_path, body.dtm_path, project_id="default")
    enqueue_job(job)
    return JobStatus(
        job_id=job.id,
        status="queued",
        progress=0,
        current_stage="queued",
        prediction_id=job.prediction_id,
        message="queued",
    )


@router.get("/{job_id}", response_model=JobStatus)
def job_status(job_id: str):
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Job not found"})
    return JobStatus(
        job_id=job.id,
        status=job.status,
        progress=job.progress,
        current_stage=job.current_stage,
        error=job.error_message,
        failed_stage=job.failed_stage,
        prediction_id=job.prediction_id,
        message=job.error_message or job.current_stage,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )
