from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field


class PredictionResult(BaseModel):
    prediction_id: str
    project_id: str
    pipeline_mode: str
    model_version: str
    label_source: str
    geojson_path: str
    thumbnail_directory: str
    metadata_path: str
    job_id: str | None = None
    summary: dict = Field(default_factory=dict)
    geojson: dict = Field(default_factory=dict)
    outputs: dict = Field(default_factory=dict)


CANONICAL_STATUSES = ("clear", "partial", "moderate", "full")


def canonical_blockage_status(status: str | None) -> str:
    raw = (status or "unknown").strip().lower()
    if raw in ("blocked", "full"):
        return "full"
    if raw == "moderate":
        return "moderate"
    if raw == "partial":
        return "partial"
    if raw == "clear":
        return "clear"
    return "clear"
