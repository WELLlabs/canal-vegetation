"""Fixed single-model registry.

The platform runs ONE approved model. The user places a single trained file in
app/config/models/ (here: a PyTorch canal-segmentation UNet, .pth). There is
deliberately no way to choose a model at runtime.

The current fixed model is a binary canal-segmentation UNet (ResNet50 encoder,
3-band RGB in, 1 class out). Blockage per reach is derived from how much of each
reach's channel the model still sees as open (see pipeline/blockage.py)."""
from __future__ import annotations
import hashlib
from pathlib import Path
from . import config

_MODEL_EXTS = {".pkl", ".joblib", ".pth", ".pt"}
_SKLEARN_EXTS = {".pkl", ".joblib"}
_TORCH_EXTS = {".pth", ".pt"}

# Architecture of the fixed segmentation model (matches the reference training).
SEG_ENCODER = "resnet50"
SEG_IN_CHANNELS = 3
SEG_CLASSES = 1
BLOCKAGE_CLASSES = ["clear", "partial", "moderate", "blocked"]
BLOCKAGE_CLASSIFIER_CLASSES = BLOCKAGE_CLASSES

_cache = {"loaded": False, "model": None}


def _discover() -> Path | None:
    if config.FIXED_MODEL_FILENAME:
        p = config.MODELS_DIR / config.FIXED_MODEL_FILENAME
        return p if p.exists() else None
    cands = sorted(p for p in config.MODELS_DIR.glob("*")
                   if p.is_file() and p.suffix.lower() in _MODEL_EXTS
                   and p.name not in (config.LINE_MODEL_FILE, config.BLOCKAGE_CLASSIFIER_FILE))
    return cands[0] if cands else None


def _sha1(p: Path, limit: int = 8_000_000) -> str:
    h = hashlib.sha1()
    with p.open("rb") as f:
        h.update(f.read(limit))
    return h.hexdigest()[:12]


def load_blockage_classifier():
    """Core-repo classifier bundle, or (None, reason). Checked against the feature contract."""
    p = config.MODELS_DIR / config.BLOCKAGE_CLASSIFIER_FILE
    if not p.exists():
        return None, None
    from .pipeline.blockage import FEATURE_NAMES
    try:
        import joblib
        b = joblib.load(p)
    except Exception as exc:
        return None, f"{p.name} could not be loaded ({exc}); vegetation thresholds used"
    if not isinstance(b, dict) or "model" not in b:
        return None, f"{p.name} is not a training.py bundle; vegetation thresholds used"
    got = list(b.get("features") or [])
    if got and got != FEATURE_NAMES:
        return None, f"{p.name} expects different features; vegetation thresholds used"
    return b, None


def scoring_info() -> dict:
    if config.SCORING_METHOD == "open_water":
        return {"method": "open_water", "label": "Open-water share (v5 U-Net)"}
    clf = (config.MODELS_DIR / config.BLOCKAGE_CLASSIFIER_FILE).exists()
    return {"method": "classifier" if clf else "vegetation_cover",
            "label": ("Trained vegetation classifier" if clf else "Vegetation cover of the canal strip"),
            "thresholds": list(config.VEG_THRESHOLDS)}


def model_info() -> dict:
    if config.SCORING_METHOD != "open_water":
        info = {"installed": True, "task": "canal_blockage", "version": "vegetation v1",
                "kind": "vegetation", "classes": BLOCKAGE_CLASSIFIER_CLASSES, "locked": True,
                "scoring": scoring_info()}
        p = config.MODELS_DIR / config.BLOCKAGE_CLASSIFIER_FILE
        info["name"] = p.name if p.exists() else "vegetation cover (5/40/70)"
        info["checksum"] = _sha1(p) if p.exists() else "-"
        return info
    p = _discover()
    if p is None:
        return {"installed": False, "task": "canal_blockage",
                "version": config.MODEL_VERSION,
                "message": "No fixed model installed. Add the approved trained "
                           "file to backend/app/config/models/."}
    ext = p.suffix.lower()
    kind = "sklearn" if ext in _SKLEARN_EXTS else "pytorch"
    info = {"installed": True, "task": "canal_blockage", "name": p.name,
            "kind": kind, "version": config.MODEL_VERSION, "checksum": _sha1(p),
            "size_mb": round(p.stat().st_size / 1e6, 2),
            "classes": BLOCKAGE_CLASSES, "locked": True}
    if kind == "pytorch":
        info["arch"] = f"unet-{SEG_ENCODER}"
        info["segments"] = "open canal channel"
    return info


def load_segmenter(device: str = "cpu"):
    """Build the fixed UNet and load its weights, once. Torch + smp are imported
    lazily so the base install stays light until inference is actually run."""
    if _cache["loaded"] and _cache["model"] is not None:
        return _cache["model"]
    p = _discover()
    if p is None:
        raise RuntimeError("No approved model installed.")
    if p.suffix.lower() not in _TORCH_EXTS:
        raise RuntimeError(f"Fixed model {p.name} is not a PyTorch segmentation "
                           "model; blockage inference expects a .pth/.pt UNet.")
    import torch
    import segmentation_models_pytorch as smp
    model = smp.Unet(encoder_name=SEG_ENCODER, encoder_weights=None,
                     in_channels=SEG_IN_CHANNELS, classes=SEG_CLASSES)
    state = torch.load(p, map_location=device, weights_only=True)
    model.load_state_dict(state)
    model.to(device).eval()
    _cache.update(loaded=True, model=model)
    return model
