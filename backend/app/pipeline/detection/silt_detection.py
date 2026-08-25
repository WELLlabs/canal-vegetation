from __future__ import annotations

import numpy as np
import rasterio
from rasterio import warp

from app.core.config import Settings, get_settings
from app.pipeline.processing.silt_classes import silt_status_from_counts


def compute_chm_silt(
    dsm_path: str,
    dtm_path: str,
    canal_mask: np.ndarray,
    mask_transform,
    crs,
    settings: Settings | None = None,
) -> dict:
    """Notebook 08 Cell 3 — reproject DSM/DTM, CHM, classify silt."""
    settings = settings or get_settings()
    mask_h, mask_w = canal_mask.shape

    with rasterio.open(dsm_path) as dsrc:
        dsm_full, _ = warp.reproject(
            source=rasterio.band(dsrc, 1),
            destination=np.zeros((mask_h, mask_w), dtype=np.float32),
            src_transform=dsrc.transform,
            src_crs=dsrc.crs,
            dst_transform=mask_transform,
            dst_crs=crs,
            resampling=warp.Resampling.bilinear,
            src_nodata=dsrc.nodata,
            dst_nodata=-9999.0,
        )

    with rasterio.open(dtm_path) as dsrc:
        dtm_full, _ = warp.reproject(
            source=rasterio.band(dsrc, 1),
            destination=np.zeros((mask_h, mask_w), dtype=np.float32),
            src_transform=dsrc.transform,
            src_crs=dsrc.crs,
            dst_transform=mask_transform,
            dst_crs=crs,
            resampling=warp.Resampling.bilinear,
            src_nodata=dsrc.nodata,
            dst_nodata=-9999.0,
        )

    valid = (dsm_full != -9999.0) & (dtm_full != -9999.0)
    chm = np.where(valid, dsm_full - dtm_full, np.nan).astype(np.float32)

    in_canal = canal_mask > 0
    chm_valid = np.isfinite(chm)
    silt_cat = np.zeros((mask_h, mask_w), dtype=np.uint8)
    silt_cat[in_canal & chm_valid & (chm < settings.silt_low_max)] = 1
    silt_cat[
        in_canal
        & chm_valid
        & (chm >= settings.silt_low_max)
        & (chm < settings.silt_mod_max)
    ] = 2
    silt_cat[
        in_canal
        & chm_valid
        & (chm >= settings.silt_mod_max)
        & (chm <= settings.silt_veg_max)
    ] = 3

    return {"chm": chm, "silt_cat": silt_cat}


def assign_silt_to_reaches(reaches: list[dict], silt_cat: np.ndarray, labels_s: np.ndarray, ds_a: int):
    """Apply notebook 08 per-reach silt rules onto blockage reaches (same canal mask)."""
    h, w = silt_cat.shape
    cat_s = None
    if labels_s.shape != silt_cat.shape:
        import cv2

        h_s, w_s = labels_s.shape
        cat_s = cv2.resize(silt_cat, (w_s, h_s), interpolation=cv2.INTER_NEAREST)
    else:
        cat_s = silt_cat

    for reach in reaches:
        rmin, cmin, rmax, cmax = reach["bbox_s"]
        cid = reach["canal_id"]
        canal_patch = labels_s[rmin:rmax, cmin:cmax] == cid
        cat_patch = cat_s[rmin:rmax, cmin:cmax]
        mh = min(canal_patch.shape[0], cat_patch.shape[0])
        mw = min(canal_patch.shape[1], cat_patch.shape[1])
        canal_patch = canal_patch[:mh, :mw]
        cat_patch = cat_patch[:mh, :mw]
        canal_px = int(canal_patch.sum())
        if canal_px < 5:
            reach["silt_status"] = "low"
            continue
        n_g = int(((cat_patch == 1) & canal_patch).sum())
        n_o = int(((cat_patch == 2) & canal_patch).sum())
        n_r_px = int(((cat_patch == 3) & canal_patch).sum())
        reach["silt_status"] = silt_status_from_counts(n_g, n_o, n_r_px, canal_px)
        reach["silt_green_frac"] = float(n_g / canal_px)
        reach["silt_orange_frac"] = float(n_o / canal_px)
        reach["silt_red_frac"] = float(n_r_px / canal_px)
    return reaches


def detect_silt(
    dsm_path: str | None,
    dtm_path: str | None,
    canal_data: dict,
    reach_pack: dict,
    settings: Settings | None = None,
) -> dict | None:
    if not dsm_path or not dtm_path:
        for r in reach_pack["reaches"]:
            r.setdefault("silt_status", "low")
        return None
    settings = settings or get_settings()
    geo = canal_data["geo"]
    out = compute_chm_silt(
        dsm_path,
        dtm_path,
        canal_data["binary"],
        geo["transform"],
        geo["crs"],
        settings,
    )
    assign_silt_to_reaches(
        reach_pack["reaches"],
        out["silt_cat"],
        reach_pack["labels_s"],
        reach_pack["ds_a"],
    )
    return out
