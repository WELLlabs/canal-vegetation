from __future__ import annotations

from pathlib import Path

import numpy as np
import torch
import segmentation_models_pytorch as smp

from app.core.config import Settings, get_settings
from app.core.errors import MODEL_NOT_AVAILABLE, AppError


def get_device() -> torch.device:
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


def autocast_ctx(device: torch.device):
    from contextlib import nullcontext

    if device.type == "cuda":
        return torch.amp.autocast("cuda")
    return nullcontext()


def imagenet_tensors(settings: Settings, device: torch.device):
    mean = torch.tensor(list(settings.imagenet_mean), device=device).view(3, 1, 1)
    std = torch.tensor(list(settings.imagenet_std), device=device).view(3, 1, 1)
    return mean, std


def tta_predict_4(model, img_t: torch.Tensor, device: torch.device) -> torch.Tensor:
    """Notebook 07: 4 rotations, average sigmoid probabilities."""
    preds = []
    with autocast_ctx(device):
        for k in range(4):
            x = torch.rot90(img_t, k, dims=[2, 3])
            prob = torch.sigmoid(model(x))
            prob = torch.rot90(prob, -k, dims=[2, 3])
            preds.append(prob)
    return torch.stack(preds).mean(dim=0)


def build_canal_unet(encoder: str = "resnet50"):
    """Architecture only — no weights, no ImageNet download."""
    return smp.Unet(encoder_name=encoder, encoder_weights=None, in_channels=3, classes=1)


def resolve_canal_weights(settings: Settings) -> Path:
    """Prefer line-tuned checkpoint, then base v5. Never fall back to random weights."""
    ordered: list[Path] = []
    if settings.model_v5_lines_path:
        ordered.append(Path(settings.model_v5_lines_path))
    ordered.append(settings.model_dir / "best_binary_unet_v5_lines.pth")
    ordered.append(settings.model_dir / settings.canal_model_fallback)
    if settings.model_v5_path:
        ordered.append(Path(settings.model_v5_path))
    ordered.append(settings.model_dir / "best_binary_unet_v5.pth")
    ordered.append(settings.model_dir / settings.canal_model_name)

    seen: set[str] = set()
    unique: list[Path] = []
    for path in ordered:
        key = str(path.resolve()) if path.is_absolute() else str(path)
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
        if path.is_file():
            return path

    searched = ", ".join(str(p) for p in unique)
    raise AppError(
        MODEL_NOT_AVAILABLE,
        "Canal model weights were not found. Place best_binary_unet_v5_lines.pth or "
        f"best_binary_unet_v5.pth under MODEL_DIR. Looked for: {searched}",
        status_code=503,
    )


class CanalModel:
    """UNet-ResNet50 binary canal segmenter from notebooks 05/07."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.device = get_device()
        self.model = build_canal_unet(self.settings.canal_encoder).to(self.device)
        weights = resolve_canal_weights(self.settings)
        self.model_version = weights.name
        self.weights_path = weights
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
