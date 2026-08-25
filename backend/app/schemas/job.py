from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator


class JobCreate(BaseModel):
    orthophoto_path: str
    dsm_path: Optional[str] = None
    dtm_path: Optional[str] = None

    @field_validator("dsm_path", "dtm_path", mode="before")
    @classmethod
    def empty_as_none(cls, value: object) -> object:
        if value == "":
            return None
        return value


class JobStatus(BaseModel):
    job_id: str
    status: str
    progress: int = 0
    current_stage: str = "queued"
    error: Optional[str] = None
    failed_stage: Optional[str] = None
    prediction_id: Optional[str] = None
    message: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
