from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), default="Untitled project")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    status: Mapped[str] = mapped_column(String(32), default="queued")
    progress: Mapped[int] = mapped_column(Integer, default=0)
    current_stage: Mapped[str] = mapped_column(String(64), default="queued")
    orthophoto_path: Mapped[str] = mapped_column(Text)
    dsm_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    dtm_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    alignment_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    project_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    prediction_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    pipeline_mode: Mapped[str | None] = mapped_column(String(32), nullable=True)
    model_version: Mapped[str | None] = mapped_column(String(128), nullable=True)
    output_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    failed_stage: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)
