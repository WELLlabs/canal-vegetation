"""Orchestrates a blockage job over one orthophoto and one bundled alignment.

For each 50 m reach whose centre falls inside the orthophoto, it reads a small
window, segments the canal with the fixed UNet, measures how much of the reach
corridor is still open channel, and classifies blockage. Results are written as
JSON, a summary, and a lon/lat GeoJSON for the map (Step 4)."""
from __future__ import annotations
import json, math
from pathlib import Path
import numpy as np
import cv2
import rasterio
from rasterio.windows import Window

from . import geo, segmenter, blockage, silt


def _pixel_coords(transform, pts):
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    rows, cols = rasterio.transform.rowcol(transform, xs, ys)
    return np.asarray(rows), np.asarray(cols)


# Status colours as BGR (OpenCV) matching the frontend palette.
_BGR = {"clear": (129, 185, 16), "partial": (11, 158, 245),
        "moderate": (22, 115, 249), "blocked": (68, 68, 239)}


def _enhance(rgb, valid=None):
    """2-98 percentile contrast stretch per channel, for readable thumbnails."""
    f = rgb.astype(np.float32)
    for ch in range(3):
        v = f[:, :, ch][valid] if valid is not None else f[:, :, ch].ravel()
        v = v[v > 0] if v.size else v
        if v.size:
            lo, hi = np.percentile(v, [2, 98])
            f[:, :, ch] = np.clip((f[:, :, ch] - lo) / (hi - lo + 1e-6) * 255, 0, 255)
    return f.astype(np.uint8)


def run_blockage(ortho_path, shp_path, model, out_dir, device="cpu",
                 progress_cb=None, canal_key="", canal_label="",
                 dsm_path=None, dtm_path=None):
    out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    img_dir = out_dir / "reaches"; img_dir.mkdir(parents=True, exist_ok=True)
    reaches, src_crs = geo.load_reaches(Path(shp_path))

    results, counts = [], {"clear": 0, "partial": 0, "moderate": 0, "blocked": 0}
    covered = 0
    canvas = None; vs = 1  # overview thumbnail + downscale factor

    with rasterio.open(ortho_path) as src:
        transform, H, W = src.transform, src.height, src.width
        px_m = abs(transform.a)
        b = src.bounds
        nbands = src.count
        dst_crs = src.crs

        # Downscaled, contrast-stretched overview for the chain view.
        vs = max(1, max(H, W) // 2400)
        vh, vw = H // vs, W // vs
        thumb = src.read(list(range(1, min(nbands, 4) + 1)),
                         out_shape=(min(nbands, 4), vh, vw))
        tvalid = (thumb[3] == 255) if thumb.shape[0] >= 4 else None
        canvas = cv2.cvtColor(
            _enhance(np.transpose(thumb[:3], (1, 2, 0)), tvalid),
            cv2.COLOR_RGB2BGR).copy()

        # reproject alignment into the ortho CRS for pixel mapping
        pts_world = [geo.reproject_pts(r["pts"], src_crs, dst_crs) for r in reaches]

        total = len(reaches)
        for i, (r, pw) in enumerate(zip(reaches, pts_world)):
            if progress_cb and i % 10 == 0:
                progress_cb(int(5 + 90 * i / max(1, total)),
                            f"Reach {i+1}/{total}")
            cx = sum(p[0] for p in pw) / len(pw)
            cy = sum(p[1] for p in pw) / len(pw)
            rec = {"id": r["id"], "canal": r["canal"], "ctype": r["ctype"],
                   "width": r["width"], "chainage": r["chainage"]}
            # lon/lat centroid + full line for the map
            (lon, lat), = geo.to_lonlat([(cx, cy)], dst_crs)
            rec["lon"], rec["lat"] = round(lon, 6), round(lat, 6)
            rec["_line"] = [[round(x, 6), round(y, 6)]
                            for x, y in geo.to_lonlat(pw, dst_crs)]

            # Covered if the reach's own extent overlaps the orthophoto bounds
            # (not just its midpoint), so reaches crossing a tile edge still count.
            rxs = [p[0] for p in pw]; rys = [p[1] for p in pw]
            if (max(rxs) < b.left or min(rxs) > b.right or
                    max(rys) < b.bottom or min(rys) > b.top):
                rec.update(status="not_covered", blockpct=None)
                results.append(rec); continue

            half = max(2, int((0.5 + r["width"] / 2) / px_m))
            margin = half + 8
            rows, cols = _pixel_coords(transform, pw)
            ins = (rows >= 0) & (rows < H) & (cols >= 0) & (cols < W)
            rows, cols = rows[ins], cols[ins]
            if len(rows) < 2:
                rec.update(status="not_covered", blockpct=None)
                results.append(rec); continue

            r0 = max(0, int(rows.min()) - margin); r1 = min(H, int(rows.max()) + margin)
            c0 = max(0, int(cols.min()) - margin); c1 = min(W, int(cols.max()) + margin)
            if r1 - r0 < 4 or c1 - c0 < 4:
                rec.update(status="not_covered", blockpct=None)
                results.append(rec); continue

            data = src.read(list(range(1, min(nbands, 4) + 1)),
                            window=Window(c0, r0, c1 - c0, r1 - r0))
            if data.shape[0] >= 4:
                valid = data[3] == 255
            else:
                valid = np.ones(data.shape[1:], bool)
            if valid.mean() < 0.3:
                rec.update(status="not_covered", blockpct=None)
                results.append(rec); continue

            rgb_chw = data[:3]
            rgb_hwc = np.transpose(rgb_chw, (1, 2, 0)).astype(np.uint8)

            # corridor mask from the reach polyline
            corridor = np.zeros(valid.shape, np.uint8)
            loc = np.array([[int(cols[k] - c0), int(rows[k] - r0)]
                            for k in range(len(rows))], np.int32)
            cv2.polylines(corridor, [loc], False, 255, max(2, 2 * half))
            corridor = ((corridor > 0) & valid).astype(np.uint8)

            prob = segmenter.segment_window(model, rgb_chw, valid, device=device)
            m = blockage.reach_blockage(prob, corridor, rgb_hwc)
            rec.update(m)
            if m["status"] in counts:
                counts[m["status"]] += 1; covered += 1
                # Save a small zoom image of the reach for the detail panel.
                crop = rgb_hwc
                ch, cw = crop.shape[:2]
                scale = 420.0 / max(ch, cw)
                if scale < 1:
                    crop = cv2.resize(crop, (max(1, int(cw * scale)),
                                             max(1, int(ch * scale))))
                cv2.imwrite(str(img_dir / f"{r['id']}.jpg"),
                            cv2.cvtColor(crop, cv2.COLOR_RGB2BGR),
                            [cv2.IMWRITE_JPEG_QUALITY, 80])
                rec["has_image"] = True
                rec["_px"] = [c0, r0, c1, r1]  # full-res window (for overview)
            results.append(rec)

    # --- Optional silt stage: only when both elevation files are supplied ---
    silt_summary = None
    if dsm_path and dtm_path and covered:
        if progress_cb:
            progress_cb(92, "Estimating silt from DSM - DTM")
        with rasterio.open(dsm_path) as dsm_src, rasterio.open(dtm_path) as dtm_src:
            dsm_crs = dsm_src.crs
            sil_counts = {"low": 0, "medium": 0, "high": 0}
            tot_vol = 0.0; depths = []; n_sil = 0
            for i, rec in enumerate(results):
                if rec.get("status") not in counts:
                    continue
                pts_dsm = geo.reproject_pts(reaches[i]["pts"], src_crs, dsm_crs)
                s = silt.reach_silt(dsm_src, dtm_src, pts_dsm, reaches[i]["width"])
                if s is None:
                    continue
                rec.update(s)
                sil_counts[s["silt_class"]] += 1
                tot_vol += s["silt_vol_m3"]; depths.append(s["silt_mean_m"]); n_sil += 1
        silt_summary = {
            "reaches": n_sil,
            "distribution": sil_counts,
            "total_volume_m3": round(tot_vol, 1),
            "mean_depth_m": round(float(sum(depths) / len(depths)), 3) if depths else 0.0,
        }

    # --- Chain overview: draw numbered, colour-coded reach boxes on the thumbnail ---
    boxes = []
    if canvas is not None and covered:
        font = cv2.FONT_HERSHEY_SIMPLEX
        vh, vw = canvas.shape[:2]
        for rec in results:
            px = rec.get("_px")
            if not px:
                continue
            x1, y1 = int(px[0] / vs), int(px[1] / vs)
            x2, y2 = int(px[2] / vs), int(px[3] / vs)
            col = _BGR.get(rec["status"], (150, 150, 150))
            cv2.rectangle(canvas, (x1, y1), (x2, y2), col, 2)
            lbl = str(rec["id"])
            cv2.putText(canvas, lbl, (x1, max(11, y1 - 3)), font, 0.42, (255, 255, 255), 3, cv2.LINE_AA)
            cv2.putText(canvas, lbl, (x1, max(11, y1 - 3)), font, 0.42, (0, 0, 0), 1, cv2.LINE_AA)
            boxes.append({"id": rec["id"], "x": x1, "y": y1,
                          "w": max(3, x2 - x1), "h": max(3, y2 - y1),
                          "status": rec["status"], "blockpct": rec.get("blockpct"),
                          "chainage": rec.get("chainage"),
                          "lon": rec.get("lon"), "lat": rec.get("lat"),
                          "silt_class": rec.get("silt_class"),
                          "silt_vol_m3": rec.get("silt_vol_m3"),
                          "has_image": True})
        cv2.imwrite(str(out_dir / "overview.png"), canvas)
        (out_dir / "boxes.json").write_text(json.dumps(
            {"tile": canal_label, "width": vw, "height": vh, "boxes": boxes}))

    if progress_cb:
        progress_cb(97, "Writing results")

    # GeoJSON (lon/lat LineStrings) for the map, colored by status
    feats = []
    for rec in results:
        line = rec.get("_line")
        if not line or len(line) < 2:
            continue
        feats.append({"type": "Feature",
                      "geometry": {"type": "LineString", "coordinates": line},
                      "properties": {k: rec.get(k) for k in
                                     ("id", "status", "blockpct", "openpct",
                                      "vegpct", "chainage", "width", "canal",
                                      "silt_class", "silt_mean_m", "silt_vol_m3",
                                      "has_image", "lon", "lat")}})
    geojson = {"type": "FeatureCollection", "features": feats}

    summary = {
        "canal": canal_key, "canal_label": canal_label,
        "total_reaches": len(results), "covered_reaches": covered,
        "distribution": counts,
        "overlap": covered > 0,
        "silt": silt_summary,
        "coverage_note": "Reaches outside this orthophoto are marked not_covered.",
    }
    if covered == 0:
        summary["message"] = (
            f"This orthophoto does not overlap the {canal_label} alignment, so no "
            "reaches could be scored. Check that the orthophoto belongs to this "
            "canal and that you selected the right canal."
        )
    clean = [{k: v for k, v in rec.items() if not k.startswith("_")}
             for rec in results]
    (out_dir / "results.json").write_text(json.dumps(clean, indent=2))
    (out_dir / "reaches.geojson").write_text(json.dumps(geojson))
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    if progress_cb:
        progress_cb(100, "Done")
    return summary
