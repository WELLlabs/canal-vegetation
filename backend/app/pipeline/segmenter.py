"""Canal segmentation using the fixed UNet (ResNet50). Tiled inference over an
arbitrary RGB window, matching the reference training recipe:
RGB/255 -> ImageNet normalise -> 512 tiles -> sigmoid -> threshold 0.4."""
from __future__ import annotations
import numpy as np

TILE = 512
THRESHOLD = 0.4
_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32).reshape(3, 1, 1)
_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32).reshape(3, 1, 1)


def segment_window(model, rgb_chw_u8: np.ndarray, valid: np.ndarray,
                   device="cpu", tile=TILE) -> np.ndarray:
    """rgb_chw_u8: (3,H,W) uint8. valid: (H,W) bool. Returns canal probability
    (H,W) float32 in [0,1], zeroed outside `valid`."""
    import torch
    _, H, W = rgb_chw_u8.shape
    rgb = rgb_chw_u8.astype(np.float32) / 255.0
    prob = np.zeros((H, W), np.float32)
    model.eval()
    with torch.no_grad():
        for r0 in range(0, H, tile):
            for c0 in range(0, W, tile):
                r1, c1 = min(r0 + tile, H), min(c0 + tile, W)
                th, tw = r1 - r0, c1 - c0
                patch = np.zeros((3, tile, tile), np.float32)
                patch[:, :th, :tw] = rgb[:, r0:r1, c0:c1]
                patch = (patch - _MEAN) / _STD
                x = torch.from_numpy(patch).unsqueeze(0).to(device)
                p = torch.sigmoid(model(x)).cpu().numpy()[0, 0]
                prob[r0:r1, c0:c1] = p[:th, :tw]
    prob[~valid] = 0.0
    return prob
