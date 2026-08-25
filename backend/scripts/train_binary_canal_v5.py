#!/usr/bin/env python3
"""
Train binary canal UNet (notebook 05 v5 logic) and write best_binary_unet_v5.pth.

Uses prepared annotation_v2 pairs (mask + raw.npy). Saves:
  - TLBC_DSM_DTM/outputs/05b_binary/best_binary_unet_v5.pth
  - canal-vegetation/backend/app/models/model_weights/best_binary_unet_v5.pth
"""

from __future__ import annotations

import os
import random
import shutil
import time
from pathlib import Path

import cv2
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import torchvision.transforms.functional as TF
from torch.utils.data import DataLoader, Dataset, WeightedRandomSampler
import segmentation_models_pytorch as smp

ANNO = Path(r"D:\Github\Canal Pipeline\TLBC_DSM_DTM\annotation_v2")
OUT_DIR = Path(r"D:\Github\Canal Pipeline\TLBC_DSM_DTM\outputs\05b_binary")
BACKEND_WEIGHTS = Path(r"D:\Github\canal-vegetation\backend\app\models\model_weights")
OUT_DIR.mkdir(parents=True, exist_ok=True)
BACKEND_WEIGHTS.mkdir(parents=True, exist_ok=True)

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
PATCH_SIZE = 512
BATCH_SIZE = 2 if DEVICE == "cpu" else 4
# CPU fallback keeps a short run so we still emit a loadable checkpoint.
# Re-run on a CUDA machine with EPOCHS=30 for production-quality weights.
EPOCHS = 6 if DEVICE == "cpu" else 30
PATIENCE = 3 if DEVICE == "cpu" else 8
SAMPLES_PER_EPOCH = 200 if DEVICE == "cpu" else 1500

IMG_MEAN = torch.tensor([0.485, 0.456, 0.406]).view(3, 1, 1)
IMG_STD = torch.tensor([0.229, 0.224, 0.225]).view(3, 1, 1)


class BinaryFocalLoss(nn.Module):
    def __init__(self, alpha=0.85, gamma=2.0):
        super().__init__()
        self.alpha = alpha
        self.gamma = gamma

    def forward(self, logits, targets):
        probs = torch.sigmoid(logits)
        bce = F.binary_cross_entropy_with_logits(logits, targets, reduction="none")
        p_t = probs * targets + (1 - probs) * (1 - targets)
        focal_weight = (1 - p_t) ** self.gamma
        alpha_t = self.alpha * targets + (1 - self.alpha) * (1 - targets)
        return (alpha_t * focal_weight * bce).mean()


class CanalPairs(Dataset):
    def __init__(self, pairs, augment=False):
        self.pairs = pairs
        self.augment = augment
        self.pos_imgs = []
        self.pos_masks = []
        for raw_f, mf in pairs:
            m = cv2.imread(mf, cv2.IMREAD_GRAYSCALE)
            if m is not None and m.max() > 0:
                self.pos_imgs.append(np.load(raw_f))
                self.pos_masks.append((m > 127).astype(np.uint8))

    def __len__(self):
        return len(self.pairs)

    def __getitem__(self, idx):
        raw_f, mf = self.pairs[idx]
        img = np.load(raw_f)
        mask = (cv2.imread(mf, cv2.IMREAD_GRAYSCALE) > 127).astype(np.uint8)
        img_t = torch.from_numpy(img.copy()).permute(2, 0, 1).float() / 255.0
        mask_t = torch.from_numpy(mask.copy()).float()
        img_t = (img_t - IMG_MEAN) / IMG_STD
        if self.augment:
            if random.random() < 0.5 and self.pos_imgs:
                si = random.randint(0, len(self.pos_imgs) - 1)
                src_t = torch.from_numpy(self.pos_imgs[si].copy()).permute(2, 0, 1).float() / 255.0
                src_t = (src_t - IMG_MEAN) / IMG_STD
                src_m = torch.from_numpy(self.pos_masks[si].copy()).float()
                k = random.choice([0, 1, 2, 3])
                if k:
                    src_t = torch.rot90(src_t, k, dims=[1, 2])
                    src_m = torch.rot90(src_m, k, dims=[0, 1])
                pm = src_m > 0.5
                img_t[:, pm] = src_t[:, pm]
                mask_t[pm] = 1.0
            if random.random() > 0.5:
                img_t = TF.hflip(img_t)
                mask_t = TF.hflip(mask_t.unsqueeze(0)).squeeze(0)
            if random.random() > 0.5:
                img_t = TF.vflip(img_t)
                mask_t = TF.vflip(mask_t.unsqueeze(0)).squeeze(0)
            k = random.choice([0, 1, 2, 3])
            if k:
                img_t = torch.rot90(img_t, k, dims=[1, 2])
                mask_t = torch.rot90(mask_t, k, dims=[0, 1])
            img_t = img_t.clamp(-3, 3)
        return img_t, mask_t.unsqueeze(0)


def collect_pairs():
    pairs = []
    for mf in sorted((ANNO / "masks").glob("*_mask.png")):
        bn = mf.name.replace("_mask.png", "")
        raw = ANNO / f"{bn}_raw.npy"
        if raw.is_file():
            pairs.append((str(raw), str(mf)))
    return pairs


def main():
    print(f"Device: {DEVICE}")
    pairs = collect_pairs()
    pos = [p for p in pairs if cv2.imread(p[1], 0).max() > 0]
    neg = [p for p in pairs if cv2.imread(p[1], 0).max() == 0]
    print(f"Pairs: {len(pairs)} (pos={len(pos)}, neg={len(neg)})")
    if not pos:
        raise SystemExit("No positive canal masks")

    random.seed(42)
    random.shuffle(pairs)
    n_val = max(8, len(pairs) // 5)
    val_pairs = pairs[:n_val]
    train_pairs = pairs[n_val:]
    # Ensure at least one positive in train
    if not any(cv2.imread(p[1], 0).max() > 0 for p in train_pairs):
        train_pairs = pos[: max(1, len(pos) - 2)] + train_pairs
        val_pairs = pos[-2:] + [p for p in val_pairs if p not in train_pairs][:n_val]

    train_ds = CanalPairs(train_pairs, augment=True)
    val_ds = CanalPairs(val_pairs, augment=False)

    weights = []
    for raw_f, mf in train_pairs:
        m = cv2.imread(mf, 0)
        weights.append(8.0 if m.max() > 0 else 1.0)
    sampler = WeightedRandomSampler(weights, num_samples=SAMPLES_PER_EPOCH, replacement=True)
    train_loader = DataLoader(train_ds, batch_size=BATCH_SIZE, sampler=sampler, num_workers=0)
    val_loader = DataLoader(val_ds, batch_size=BATCH_SIZE, shuffle=False, num_workers=0)

    model = smp.Unet(
        encoder_name="resnet50",
        encoder_weights="imagenet",
        in_channels=3,
        classes=1,
    ).to(DEVICE)

    focal_fn = BinaryFocalLoss(alpha=0.85, gamma=2.0)
    dice_fn = smp.losses.DiceLoss(mode="binary", from_logits=True)

    def loss_fn(logits, targets):
        return focal_fn(logits, targets) + dice_fn(logits, targets)

    opt = torch.optim.AdamW(model.parameters(), lr=5e-4, weight_decay=1e-4)
    best_path = OUT_DIR / "best_binary_unet_v5.pth"
    best_iou = -1.0
    wait = 0

    print(f"Train {len(train_ds)} | Val {len(val_ds)} | epochs={EPOCHS} | save={best_path}")
    for epoch in range(1, EPOCHS + 1):
        t0 = time.time()
        model.train()
        tr = 0.0
        for imgs, masks in train_loader:
            imgs, masks = imgs.to(DEVICE), masks.to(DEVICE)
            opt.zero_grad()
            logits = model(imgs)
            loss = loss_fn(logits, masks)
            loss.backward()
            opt.step()
            tr += loss.item()
        tr /= max(1, len(train_loader))

        model.eval()
        tp = fp = fn = 0.0
        with torch.no_grad():
            for imgs, masks in val_loader:
                imgs, masks = imgs.to(DEVICE), masks.to(DEVICE)
                pred = (torch.sigmoid(model(imgs)) > 0.5).float()
                tp += (pred * masks).sum().item()
                fp += (pred * (1 - masks)).sum().item()
                fn += ((1 - pred) * masks).sum().item()
        iou = tp / (tp + fp + fn + 1e-6)
        marker = ""
        if iou > best_iou:
            best_iou = iou
            wait = 0
            torch.save(model.state_dict(), best_path)
            shutil.copy2(best_path, BACKEND_WEIGHTS / "best_binary_unet_v5.pth")
            marker = " ** saved"
        else:
            wait += 1
        print(
            f"E{epoch:02d} loss={tr:.4f} IoU={iou:.3f} best={best_iou:.3f} "
            f"{time.time()-t0:.0f}s{marker}"
        )
        if wait >= PATIENCE:
            print("Early stop")
            break

    if not best_path.exists():
        torch.save(model.state_dict(), best_path)
        shutil.copy2(best_path, BACKEND_WEIGHTS / "best_binary_unet_v5.pth")
    size_mb = best_path.stat().st_size / 1e6
    print(f"DONE: {best_path} ({size_mb:.1f} MB) IoU={best_iou:.3f}")
    print(f"Copied to {BACKEND_WEIGHTS / 'best_binary_unet_v5.pth'}")


if __name__ == "__main__":
    main()
