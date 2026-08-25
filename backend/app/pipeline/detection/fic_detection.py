from __future__ import annotations

import cv2
import numpy as np

from app.core.config import Settings, get_settings
from app.pipeline.detection.canal_detection import predict_probability_mosaic
from app.pipeline.models.fic_model import FicModel


def detect_fic(
    orthophoto_path: str,
    model: FicModel | None = None,
    settings: Settings | None = None,
) -> dict | None:
    """Notebook 06 Cell 8 full-mosaic FIC inference."""
    settings = settings or get_settings()
    if model is None:
        if not FicModel.weights_exist(settings):
            return None
        model = FicModel(settings)

    pred_avg, geo = predict_probability_mosaic(orthophoto_path, model.predict_tile, settings)
    fic_raw = (pred_avg > settings.fic_threshold).astype(np.uint8)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    fic_mask = cv2.morphologyEx(fic_raw, cv2.MORPH_OPEN, kernel, iterations=1)
    fic_mask = cv2.morphologyEx(fic_mask, cv2.MORPH_CLOSE, kernel, iterations=1)

    n_labels, labels, stats, _ = cv2.connectedComponentsWithStats(fic_mask, connectivity=8)
    fic_filtered = np.zeros_like(fic_mask)
    for i in range(1, n_labels):
        area = stats[i, cv2.CC_STAT_AREA]
        if area >= settings.fic_min_component_area:
            fic_filtered[labels == i] = 1

    return {
        "mask": fic_filtered.astype(np.uint8),
        "prob": pred_avg,
        "geo": geo,
    }
