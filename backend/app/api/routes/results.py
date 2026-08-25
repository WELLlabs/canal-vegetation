from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.core.config import get_settings
from app.services.job_service import get_job
from app.services.result_service import frontend_payload

router = APIRouter(prefix="/jobs", tags=["results"])


@router.get("/{job_id}/results")
def job_results(job_id: str):
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status == "failed":
        raise HTTPException(
            status_code=409,
            detail={"code": job.error_code or "PREDICTION_FAILED", "message": job.error_message or "Job failed"},
        )
    if job.status != "completed":
        raise HTTPException(status_code=409, detail={"code": "NOT_READY", "message": f"Job is {job.status}"})
    return frontend_payload(job)


@router.get("/{job_id}/files/{file_path:path}")
def job_file(job_id: str, file_path: str):
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    settings = get_settings()
    root = (Path(settings.output_dir) / job_id).resolve()
    target = (root / file_path).resolve()
    if not str(target).startswith(str(root)) or not target.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(target)
