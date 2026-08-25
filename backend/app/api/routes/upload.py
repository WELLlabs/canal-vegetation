from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.core.config import get_settings
from app.pipeline.io.storage import get_storage

router = APIRouter(prefix="/uploads", tags=["uploads"])

ALLOWED = {".tif", ".tiff", ".jpg", ".jpeg", ".png", ".webp"}


@router.post("")
async def create_upload(
    orthophoto: UploadFile = File(...),
    dsm: UploadFile | None = File(None),
    dtm: UploadFile | None = File(None),
):
    settings = get_settings()
    storage = get_storage(settings)
    uid = str(uuid.uuid4())
    dest_dir = Path(settings.upload_dir) / uid
    dest_dir.mkdir(parents=True, exist_ok=True)

    def save(upload: UploadFile, name: str) -> str:
        suffix = Path(upload.filename or name).suffix.lower() or ".tif"
        if suffix not in ALLOWED:
            raise HTTPException(status_code=400, detail=f"Unsupported file type: {suffix}")
        local_path = dest_dir / f"{name}{suffix}"
        with local_path.open("wb") as f:
            shutil.copyfileobj(upload.file, f)
        if settings.storage_backend.lower() == "s3":
            return storage.save_file(local_path, f"uploads/{uid}/{name}{suffix}")
        return str(local_path.resolve())

    payload = {
        "upload_id": uid,
        "orthophoto_path": save(orthophoto, "orthophoto"),
        "dsm_path": save(dsm, "dsm") if dsm is not None and dsm.filename else None,
        "dtm_path": save(dtm, "dtm") if dtm is not None and dtm.filename else None,
        "storage": settings.storage_backend,
    }
    return payload
