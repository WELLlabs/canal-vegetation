from __future__ import annotations

from pathlib import Path

import numpy as np
import torch
import segmentation_models_pytorch as smp

from app.core.config import Settings, get_settings
from app.pipeline.models.canal_model import (
    autocast_ctx,
    get_device,
    imagenet_tensors,
    resolve_weight_path,
    tta_predict_4,
)


class FicModel:
    """UNet-ResNet34 FIC segmenter from notebook 06."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.device = get_device()
        self.model = smp.Unet(
            encoder_name=self.settings.fic_encoder,
            encoder_weights=None,
            in_channels=3,
            classes=1,
        ).to(self.device)
        weights = resolve_weight_path(self.settings, self.settings.fic_model_name)
        try:
            state = torch.load(weights, map_location=self.device, weights_only=True)
        except TypeError:
            state = torch.load(weights, map_location=self.device)
        self.model.load_state_dict(state)
        self.model.eval()
        self.mean, self.std = imagenet_tensors(self.settings, self.device)

    def predict_tile(self, rgb_chw: np.ndarray) -> np.ndarray:
        img_t = torch.from_numpy(rgb_chw.astype(np.float32) / 255.0).to(self.device)
        img_t = (img_t - self.mean) / self.std
        with torch.inference_mode():
            prob = tta_predict_4(self.model, img_t.unsqueeze(0), self.device)
            return prob.cpu().numpy()[0, 0].astype(np.float32)

    @staticmethod
    def weights_exist(settings: Settings | None = None) -> bool:
        settings = settings or get_settings()
        return (settings.model_dir / settings.fic_model_name).is_file() or Path(
            settings.fic_model_name
        ).is_file()
