from __future__ import annotations

from app.pipeline.models.canal_model import CanalModel

_canal: CanalModel | None = None


def get_canal_model() -> CanalModel:
    global _canal
    if _canal is None:
        _canal = CanalModel()
    return _canal


def reset_canal_model() -> None:
    global _canal
    _canal = None
