from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import get_settings
from app.core.errors import AppError
from app.models.database_models import Job, Project
from app.models.db import SessionLocal
from app.services.pipeline_service import run_pipeline

logger = logging.getLogger(__name__)


def create_project(name: str = "Untitled project") -> Project:
    project = Project(id=str(uuid.uuid4()), name=name or "Untitled project")
    db = SessionLocal()
    try:
        db.add(project)
        db.commit()
        db.refresh(project)
        return project
    finally:
        db.close()


def get_project(project_id: str) -> Project | None:
    db = SessionLocal()
    try:
        return db.get(Project, project_id)
    finally:
        db.close()


def list_projects() -> list[Project]:
    db = SessionLocal()
    try:
        return list(db.query(Project).order_by(Project.created_at.desc()).all())
    finally:
        db.close()


def ensure_default_project() -> Project:
    db = SessionLocal()
    try:
        existing = db.get(Project, "default")
        if existing:
            return existing
        p = Project(id="default", name="Default")
        db.add(p)
        db.commit()
        db.refresh(p)
        return p
    finally:
        db.close()


def create_job(
    orthophoto_path: str,
    dsm_path: str | None = None,
    dtm_path: str | None = None,
    alignment_path: str | None = None,
    project_id: str | None = None,
    prediction_id: str | None = None,
) -> Job:
    project_id = project_id or "default"
    prediction_id = prediction_id or str(uuid.uuid4())
    job = Job(
        id=str(uuid.uuid4()),
        status="queued",
        progress=0,
        current_stage="queued",
        orthophoto_path=orthophoto_path,
        dsm_path=dsm_path,
        dtm_path=dtm_path,
        alignment_path=alignment_path,
        project_id=project_id,
        prediction_id=prediction_id,
        pipeline_mode="ortho_plus_alignment" if alignment_path else "ortho_only",
    )
    db = SessionLocal()
    try:
        db.add(job)
        db.commit()
        db.refresh(job)
        return job
    finally:
        db.close()


def get_job(job_id: str) -> Job | None:
    db = SessionLocal()
    try:
        return db.get(Job, job_id)
    finally:
        db.close()


def get_job_by_prediction(prediction_id: str) -> Job | None:
    db = SessionLocal()
    try:
        return db.query(Job).filter(Job.prediction_id == prediction_id).order_by(Job.created_at.desc()).first()
    finally:
        db.close()


def update_job(job_id: str, **fields) -> None:
    db = SessionLocal()
    try:
        job = db.get(Job, job_id)
        if job is None:
            return
        for k, v in fields.items():
            setattr(job, k, v)
        job.updated_at = datetime.now(timezone.utc)
        db.commit()
    finally:
        db.close()


def enqueue_job(job: Job) -> None:
    settings = get_settings()
    if settings.use_celery:
        from app.workers.tasks import run_job_task

        run_job_task.delay(job.id)
    else:
        import threading

        threading.Thread(target=execute_job, args=(job.id,), daemon=True).start()


def execute_job(job_id: str) -> dict:
    job = get_job(job_id)
    if job is None:
        raise ValueError(f"Unknown job {job_id}")
    settings = get_settings()
    update_job(job_id, status="running", current_stage="Loading canal model", progress=1)

    def progress_cb(pct: int, stage: str) -> None:
        status = "completed" if stage == "completed" else "running"
        update_job(job_id, progress=pct, current_stage=stage, status=status)

    try:
        from app.pipeline.io.storage import get_storage

        storage = get_storage(settings)
        ortho = storage.local_path(job.orthophoto_path)
        alignment = storage.local_path(job.alignment_path) if job.alignment_path else None
        result = run_pipeline(
            job_id=job_id,
            orthophoto_path=ortho,
            alignment_path=alignment,
            project_id=job.project_id,
            prediction_id=job.prediction_id,
            config=settings,
            progress_cb=progress_cb,
        )
        pred_dir = Path(settings.project_root) / (job.project_id or "default") / "predictions" / (job.prediction_id or job_id)
        result_path = str(pred_dir / "result.json")
        update_job(
            job_id,
            status="completed",
            progress=100,
            current_stage="completed",
            output_path=str(pred_dir),
            result_path=result_path,
            model_version=result.get("model_version"),
            pipeline_mode=result.get("pipeline_mode"),
            error_message=None,
            error_code=None,
            failed_stage=None,
        )
        return result
    except AppError as exc:
        stage = (get_job(job_id) or job).current_stage
        logger.exception("Job %s failed at %s", job_id, stage)
        update_job(
            job_id,
            status="failed",
            error_message=exc.message,
            error_code=exc.code,
            failed_stage=stage,
        )
        raise
    except Exception as exc:
        stage = (get_job(job_id) or job).current_stage
        logger.exception("Job %s failed at %s", job_id, stage)
        update_job(
            job_id,
            status="failed",
            error_message="Prediction failed. See server logs for details.",
            error_code="PREDICTION_FAILED",
            failed_stage=stage,
        )
        raise
