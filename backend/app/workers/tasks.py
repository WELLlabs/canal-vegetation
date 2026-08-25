from __future__ import annotations

from celery import Celery
from celery.signals import worker_process_init

from app.core.config import get_settings
from app.core.logging import setup_logging

settings = get_settings()
celery_app = Celery(
    "canal_pipeline",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_track_started=True,
    worker_prefetch_multiplier=1,
)


@worker_process_init.connect
def _load_models(**kwargs):
    setup_logging()
    from app.pipeline.models.registry import get_canal_model

    try:
        get_canal_model()
    except Exception:
        pass


@celery_app.task(name="pipeline.run_job")
def run_job_task(job_id: str) -> dict:
    from app.services.job_service import execute_job

    return execute_job(job_id)
