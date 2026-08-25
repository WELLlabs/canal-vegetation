from __future__ import annotations

import cv2
import numpy as np
import rasterio
from rasterio.windows import Window

from app.core.config import Settings, get_settings
from app.pipeline.processing.blockage_scoring import score_reach
from app.pipeline.processing.reach_analysis import assign_global_chainage, extract_reaches


def compute_reach_features_and_blockage(rgb_patch, canal_mask_patch):
    """Notebook 07 Cell 9."""
    canal_px = canal_mask_patch > 0
    if canal_px.sum() < 10:
        return None, None

    r = rgb_patch[:, :, 0].astype(np.float32)
    g = rgb_patch[:, :, 1].astype(np.float32)
    b = rgb_patch[:, :, 2].astype(np.float32)
    hsv_patch = cv2.cvtColor(rgb_patch, cv2.COLOR_RGB2HSV)
    h_ch = hsv_patch[:, :, 0].astype(np.float32)
    s_ch = hsv_patch[:, :, 1].astype(np.float32)
    v_ch = hsv_patch[:, :, 2].astype(np.float32)

    exg = 2.0 * g - r - b
    denom = g + r - b + 1e-6
    vari = np.where(np.abs(denom) > 1, (g - r) / denom, 0)
    green_hsv = (h_ch >= 35) & (h_ch <= 85) & (s_ch > 40) & (v_ch > 50)
    veg_mask = ((exg > 25) | ((vari > 0.1) & green_hsv)) & canal_px
    water_mask = (v_ch < 120) & (b > r) & (s_ch > 15) & canal_px
    bright_mask = (v_ch > 180) & canal_px
    silt_like_mask = bright_mask & (s_ch < 50)
    gray = 0.299 * r + 0.587 * g + 0.114 * b

    n_px = max(1, int(canal_px.sum()))
    feats = {
        "veg_frac": float(veg_mask.sum() / n_px),
        "green_hsv_frac": float((green_hsv & canal_px).sum() / n_px),
        "exg_mean": float(exg[canal_px].mean()),
        "vari_mean": float(vari[canal_px].mean()),
        "water_frac": float(water_mask.sum() / n_px),
        "bright_frac": float(bright_mask.sum() / n_px),
        "silt_like_frac": float(silt_like_mask.sum() / n_px),
        "gray_std": float(gray[canal_px].std()),
        "v_mean": float(v_ch[canal_px].mean()),
        "s_mean": float(s_ch[canal_px].mean()),
    }
    return feats, (veg_mask | silt_like_mask).astype(np.uint8)


def centerline_blocked_length(canal_patch, blocked_mask, reach_length_m):
    skel = skeletonize_safe(canal_patch)
    skel_count = int(skel.sum())
    if skel_count == 0:
        return 0.0, 0.0
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    blocked_dil = cv2.dilate(blocked_mask.astype(np.uint8), kernel, iterations=1)
    blocked_skel = int(((skel > 0) & (blocked_dil > 0)).sum())
    blocked_frac = blocked_skel / max(1, skel_count)
    return float(reach_length_m * blocked_frac), float(blocked_frac)


def skeletonize_safe(canal_patch):
    from skimage.morphology import skeletonize

    return skeletonize(canal_patch > 0).astype(np.uint8)


def detect_sd(rgb_patch, canal_mask_patch):
    """Notebook 07 Cell 17 structural damage features."""
    canal_px = canal_mask_patch > 0
    if canal_px.sum() < 20:
        return None
    gray = cv2.cvtColor(rgb_patch, cv2.COLOR_RGB2GRAY)
    edges = cv2.Canny(gray, 80, 200)
    edge_density = edges[canal_px].sum() / (255.0 * canal_px.sum())
    gray_f = gray.astype(np.float32)
    lm = cv2.blur(gray_f, (7, 7))
    lv = cv2.blur((gray_f - lm) ** 2, (7, 7))
    tex_var = lv[canal_px].mean()
    gx = cv2.Sobel(gray_f, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray_f, cv2.CV_32F, 0, 1, ksize=3)
    grad = np.sqrt(gx**2 + gy**2)[canal_px].mean()
    sat = cv2.cvtColor(rgb_patch, cv2.COLOR_RGB2HSV)[:, :, 1][canal_px].astype(np.float32)
    low_sat = (sat < 30).sum() / canal_px.sum()
    return {
        "edge_density": float(edge_density),
        "tex_var": float(tex_var),
        "grad": float(grad),
        "low_sat": float(low_sat),
    }


def _score_structural(sd: dict) -> tuple[bool, float]:
    sc = 0.0
    if sd["edge_density"] > 0.35:
        sc += 2.0
    elif sd["edge_density"] > 0.25:
        sc += 1.0
    if sd["grad"] > 80:
        sc += 2.0
    elif sd["grad"] > 60:
        sc += 1.0
    if sd["low_sat"] > 0.7:
        sc += 2.0
    elif sd["low_sat"] > 0.5:
        sc += 1.0
    if sd["tex_var"] > 1500:
        sc += 1.0
    return sc >= 4.0, sc


def _read_reach_rgb(src, reach, ds: int, labels_s, ds_a: int):
    H, W = src.height, src.width
    r_min, c_min, r_max, c_max = reach["bbox"]
    fr_min, fc_min = r_min * ds, c_min * ds
    fr_max, fc_max = min(r_max * ds, H), min(c_max * ds, W)
    rh = fr_max - fr_min
    rw = fc_max - fc_min
    if rh < 8 or rw < 8:
        return None, None
    data = src.read([1, 2, 3], window=Window(fc_min, fr_min, rw, rh))
    rgb_full = data.transpose(1, 2, 0)
    ds_total = ds * ds_a
    crop_h = (rh // ds_total) * ds_total
    crop_w = (rw // ds_total) * ds_total
    if crop_h < ds_total or crop_w < ds_total:
        return None, None
    rgb_sm = (
        rgb_full[:crop_h, :crop_w]
        .reshape(crop_h // ds_total, ds_total, crop_w // ds_total, ds_total, 3)
        .mean(axis=(1, 3))
        .astype(np.uint8)
    )
    rmin_s, cmin_s, rmax_s, cmax_s = reach["bbox_s"]
    cid = reach["canal_id"]
    canal_patch = (
        labels_s[rmin_s : rmin_s + rgb_sm.shape[0], cmin_s : cmin_s + rgb_sm.shape[1]] == cid
    ).astype(np.uint8)
    if canal_patch.shape != rgb_sm.shape[:2]:
        mh = min(canal_patch.shape[0], rgb_sm.shape[0])
        mw = min(canal_patch.shape[1], rgb_sm.shape[1])
        canal_patch = canal_patch[:mh, :mw]
        rgb_sm = rgb_sm[:mh, :mw]
    return rgb_sm, canal_patch


def classify_reaches(orthophoto_path: str, canal_data: dict, reach_pack: dict, settings: Settings | None = None):
    settings = settings or get_settings()
    ds = settings.downscale_factor
    reaches = reach_pack["reaches"]
    labels_s = reach_pack["labels_s"]
    ds_a = reach_pack["ds_a"]

    with rasterio.open(orthophoto_path) as src:
        for reach in reaches:
            rgb_sm, canal_patch = _read_reach_rgb(src, reach, ds, labels_s, ds_a)
            if rgb_sm is None:
                reach["status"] = "unknown"
                reach["features"] = None
                reach["blocked_distance_m"] = 0.0
                reach["blocked_fraction"] = 0.0
                reach["damage"] = False
                continue

            feats, blocked_mask = compute_reach_features_and_blockage(rgb_sm, canal_patch)
            reach["features"] = feats
            if feats is None:
                reach["status"] = "unknown"
                reach["blocked_distance_m"] = 0.0
                reach["blocked_fraction"] = 0.0
                reach["damage"] = False
                continue

            blocked_dist, blocked_frac = centerline_blocked_length(
                canal_patch, blocked_mask, reach["length_m"]
            )
            scored = score_reach(feats, blocked_frac)
            reach.update(scored)
            reach["blocked_distance_m"] = blocked_dist
            reach["blocked_fraction"] = blocked_frac
            reach["blockage_percentage"] = float(blocked_frac * 100.0)

            if reach["status"] == "blocked":
                reach["damage"] = False
                reach["sd_score"] = 0.0
            else:
                sd = detect_sd(rgb_sm, canal_patch)
                if sd is None:
                    reach["damage"] = False
                    reach["sd_score"] = 0.0
                else:
                    damaged, sc = _score_structural(sd)
                    reach["damage"] = bool(damaged)
                    reach["sd_score"] = float(sc)

    assign_global_chainage(reaches)
    return reaches


def detect_blockages(orthophoto_path: str, canal_data: dict, settings: Settings | None = None) -> dict:
    settings = settings or get_settings()
    px_m_mask = canal_data["px_m"] * settings.downscale_factor
    pack = extract_reaches(
        canal_data["binary"],
        px_m_mask,
        ds_a=settings.analysis_downscale,
        reach_len_px=settings.reach_len_px,
    )
    classify_reaches(orthophoto_path, canal_data, pack, settings)
    return pack
