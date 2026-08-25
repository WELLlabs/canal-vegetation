from typing import Any, Optional

from pydantic import BaseModel


class PipelineSummary(BaseModel):
    total_reaches: int = 0
    clear: int = 0
    partial: int = 0
    blocked: int = 0
    silt_low: int = 0
    silt_medium: int = 0
    silt_high: int = 0
    damage: int = 0


class JobResult(BaseModel):
    job_id: str
    status: str
    summary: PipelineSummary
    outputs: dict[str, Any]
    geojson: dict[str, Any]
    features: list[dict[str, Any]] = []
