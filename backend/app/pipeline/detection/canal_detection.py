from __future__ import annotations

import logging

import numpy as np
import rasterio
from app.core.config import Settings, get_settings
from app.pipeline.io.raster_reader import iter_tile_offsets, open_meta, read_window_rgba
from app.pipeline.models.canal_model import CanalModel
from app.pipeline.processing.postprocessing import classify_canal_components
from app.pipeline.geospatial.corridor import apply_corridor_filter, build_corridor, build_corridor_from_lines

logger = logging.getLogger(__name__)


def predict_probability_mosaic(
    fpath: str,
    predict_fn,
    settings: Settings | None = None,
    progress_cb=None,
) -> tuple[np.ndarray, dict]:
    """
    Windowed overlapping inference + overlap averaging + downscale.
    Same algorithm as notebooks 05 Cell 5 / 06 Cell 8 / 07 Cell 3.
    """
    settings = settings or get_settings()
    tile = settings.tile_size
    step = settings.tile_step
    ds = settings.downscale_factor
    meta = open_meta(fpath)
    W, H = meta.width, meta.height
    out_h, out_w = H // ds, W // ds
    tile_ds = tile // ds
    pred_sum = np.zeros((out_h, out_w), dtype=np.float32)
    count_map = np.zeros((out_h, out_w), dtype=np.float32)
    if W >= tile and H >= tile:
        n_tiles = ((H - tile) // step + 1) * ((W - tile) // step + 1)
    else:
        n_tiles = 1
    done = 0

    with rasterio.open(fpath) as src:
        for col, row in iter_tile_offsets(W, H, tile, step):
            rgb, valid = read_window_rgba(src, col, row, tile, tile)
            if valid.sum() < tile * tile * settings.min_valid_frac:
                done += 1
                continue
            prob = predict_fn(rgb)
            prob = prob.copy()
            h, w = prob.shape
            valid_use = valid[:h, :w]
            prob[~valid_use] = 0
            valid_f = valid_use.astype(np.float32)
            if h != tile or w != tile:
                done += 1
                continue
            prob_ds = prob.reshape(tile_ds, ds, tile_ds, ds).mean(axis=(1, 3))
            valid_ds = valid_f.reshape(tile_ds, ds, tile_ds, ds).mean(axis=(1, 3))
            r0 = row // ds
            c0 = col // ds
            r1 = min(r0 + tile_ds, out_h)
            c1 = min(c0 + tile_ds, out_w)
            pred_sum[r0:r1, c0:c1] += prob_ds[: r1 - r0, : c1 - c0]
            count_map[r0:r1, c0:c1] += valid_ds[: r1 - r0, : c1 - c0]
            done += 1
            if progress_cb and n_tiles and (done % 25 == 0 or done == n_tiles):
                pct = 12 + int(32 * done / max(1, n_tiles))
                progress_cb(min(44, pct), f"Canal inference {done}/{n_tiles} tiles")

    pred_avg = np.divide(pred_sum, count_map, out=np.zeros_like(pred_sum), where=count_map > 0)
    new_transform = rasterio.transform.Affine(
        meta.transform.a * ds,
        meta.transform.b,
        meta.transform.c,
        meta.transform.d,
        meta.transform.e * ds,
        meta.transform.f,
    )
    geo = {
        "crs": meta.crs,
        "transform": new_transform,
        "width": out_w,
        "height": out_h,
        "orig_W": W,
        "orig_H": H,
        "pixel_size_m": meta.pixel_size_m,
        "px_m_ds": meta.pixel_size_m * ds,
    }
    return pred_avg.astype(np.float32), geo


def detect_canals(
    orthophoto_path: str,
    model: CanalModel | None = None,
    settings: Settings | None = None,
    alignment_path: str | None = None,
    alignment_lines: list | None = None,
    progress_cb=None,
) -> dict:
    settings = settings or get_settings()
    model = model or CanalModel(settings)
    pred_avg, geo = predict_probability_mosaic(
        orthophoto_path, model.predict_tile, settings, progress_cb=progress_cb
    )
    canal_raw = (pred_avg > settings.canal_threshold).astype(np.uint8)
    px_m_ds = geo["px_m_ds"]
    canal_only, fic_candidate, rejected, counts = classify_canal_components(
        canal_raw, px_m_ds, settings
    )
    corridor = None
    if alignment_lines:
        corridor = build_corridor_from_lines(
            orthophoto_path,
            canal_only.shape,
            settings.downscale_factor,
            alignment_lines,
            settings.corridor_buffer_m,
        )
    else:
        shp = alignment_path or settings.corridor_shapefile
        corridor = build_corridor(
            orthophoto_path,
            canal_only.shape,
            settings.downscale_factor,
            shp,
            settings.corridor_buffer_m,
        )
    if corridor is not None:
        canal_only = apply_corridor_filter(canal_only, corridor)
        logger.info("Applied alignment corridor filter")

    logger.info("Canal components: %s", counts)
    return {
        "binary": canal_only,
        "prob": pred_avg,
        "raw": canal_raw,
        "fic_candidate": fic_candidate,
        "rejected": rejected,
        "filter_counts": counts,
        "geo": geo,
        "fpath": orthophoto_path,
        "px_m": geo["pixel_size_m"],
        "model_version": getattr(model, "model_version", "unknown"),
    }
