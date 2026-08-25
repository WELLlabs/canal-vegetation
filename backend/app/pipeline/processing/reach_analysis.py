from __future__ import annotations

import cv2
import numpy as np
from skimage.morphology import skeletonize


def extract_reaches(canal_bin: np.ndarray, px_m_mask: float, ds_a: int = 4, reach_len_px: int = 100):
    """Notebook 07 Cell 8 — centerlines, widths, reach segmentation."""
    h, w = canal_bin.shape
    h_s = h // ds_a
    w_s = w // ds_a
    canal_s = cv2.resize(canal_bin, (w_s, h_s), interpolation=cv2.INTER_NEAREST)
    px_m_a = px_m_mask * ds_a

    dist = cv2.distanceTransform(canal_s, cv2.DIST_L2, 5)
    width_arr = dist * 2.0 * px_m_a

    skel = skeletonize(canal_s > 0).astype(np.uint8)
    n_cc, labels_s = cv2.connectedComponents(canal_s, connectivity=8)
    sr, sc = np.where(skel > 0)
    sl = labels_s[sr, sc]

    reaches = []
    for cid in range(1, n_cc):
        m = sl == cid
        cr = sr[m]
        cc_arr = sc[m]
        if len(cr) < 10:
            continue

        pts = np.column_stack([cr, cc_arr])
        n_r = max(1, len(pts) // reach_len_px)

        for ri in range(n_r):
            s = ri * reach_len_px
            e = min((ri + 1) * reach_len_px, len(pts))
            rp = pts[s:e]

            rmin_s = max(0, rp[:, 0].min() - 10)
            cmin_s = max(0, rp[:, 1].min() - 10)
            rmax_s = min(h_s, rp[:, 0].max() + 10)
            cmax_s = min(w_s, rp[:, 1].max() + 10)

            rc = labels_s[rmin_s:rmax_s, cmin_s:cmax_s] == cid
            cpx = int(rc.sum())
            if cpx < 10:
                continue

            wv = width_arr[rmin_s:rmax_s, cmin_s:cmax_s][rc]
            reaches.append(
                {
                    "canal_id": int(cid),
                    "reach_idx": ri,
                    "bbox": (
                        rmin_s * ds_a,
                        cmin_s * ds_a,
                        min(h, rmax_s * ds_a),
                        min(w, cmax_s * ds_a),
                    ),
                    "bbox_s": (int(rmin_s), int(cmin_s), int(rmax_s), int(cmax_s)),
                    "center": (int(rp[:, 0].mean() * ds_a), int(rp[:, 1].mean() * ds_a)),
                    "canal_px": cpx,
                    "avg_width_m": float(wv.mean()),
                    "max_width_m": float(wv.max()),
                    "length_m": float(len(rp) * px_m_a),
                }
            )

    lbl_dtype = np.uint8 if n_cc < 256 else np.uint16
    return {
        "reaches": reaches,
        "labels_s": labels_s.astype(lbl_dtype),
        "ds_a": ds_a,
        "shape_s": (h_s, w_s),
        "n_canals": n_cc - 1,
    }


def assign_global_chainage(reaches: list[dict]) -> None:
    """Notebook 07 Cell 16."""
    if not reaches:
        return
    centers = np.array([[r["center"][0], r["center"][1]] for r in reaches], dtype=np.float32)
    centered = centers - centers.mean(axis=0, keepdims=True)
    if len(reaches) >= 2:
        _, _, vh = np.linalg.svd(centered, full_matrices=False)
        proj = centered @ vh[0]
    else:
        proj = centers[:, 0]
    chainage = 0.0
    for seq, idx in enumerate(np.argsort(proj)):
        r = reaches[int(idx)]
        r["global_reach_idx"] = int(seq)
        r["chainage_m"] = chainage
        r["chainage_start_m"] = chainage
        chainage += r["length_m"]
        r["chainage_end_m"] = chainage
