from __future__ import annotations

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.models.database_models import Base

_engine = None
_SessionLocal = None

_JOB_EXTRA = {
    "alignment_path": "TEXT",
    "project_id": "VARCHAR(36)",
    "prediction_id": "VARCHAR(36)",
    "pipeline_mode": "VARCHAR(32)",
    "model_version": "VARCHAR(128)",
    "error_code": "VARCHAR(64)",
}


def _migrate_sqlite(engine) -> None:
    if not str(engine.url).startswith("sqlite"):
        return
    with engine.begin() as conn:
        rows = conn.execute(text("PRAGMA table_info(jobs)")).fetchall()
        names = {r[1] for r in rows}
        for col, spec in _JOB_EXTRA.items():
            if col not in names:
                conn.execute(text(f"ALTER TABLE jobs ADD COLUMN {col} {spec}"))


def get_engine():
    global _engine, _SessionLocal
    if _engine is None:
        settings = get_settings()
        connect_args = {}
        if settings.database_url.startswith("sqlite"):
            connect_args = {"check_same_thread": False}
        _engine = create_engine(settings.database_url, connect_args=connect_args)
        Base.metadata.create_all(_engine)
        _migrate_sqlite(_engine)
        _SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False)
    return _engine


def SessionLocal():
    get_engine()
    return _SessionLocal()
