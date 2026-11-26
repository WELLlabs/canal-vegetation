"""
Canal centreline extraction from drone GeoTIFFs (v2).

  python canal_extract_light.py train   --config canal_config.yaml   # learn from ground-truth canals
  python canal_extract_light.py predict --config canal_config.yaml --image test.tif [--truth truth.shp]
  python canal_extract_light.py cv      --config canal_config.yaml   # leave-one-site-out accuracy table

train:   cut tiles around the ground-truth lines of every site (scale-jittered, per-site label widths),
         hold out spatial blocks for validation, fine-tune a pretrained U-Net and keep the checkpoint
         with the best validation IoU -> <work_dir>/model.pt
predict: read only the all-India lines under the image (bbox read), U-Net canal probability inside
         the buffer (batched, flip test-time augmentation), least-cost trace of every line with a
         wider retry where the first trace finds no canal, join traced branches at junctions,
         smooth, then cut into reaches with a confidence score each.
         Writes <name>.shp (lines), <name>_reaches.shp (reaches + confidence), <name>_prob.tif and
         <name>.zip (the lines shapefile zipped, ready to upload to the blockage app).
cv:      for every training site: train on the others, predict on it, compare with its truth.
         Writes <work_dir>/cv/cv_results.csv. This is the honest accuracy number for unseen sites.

pip install geopandas rasterio shapely scikit-image scipy pyyaml gdown segmentation-models-pytorch
"""
import argparse
import csv
import functools
import hashlib
import os
import re
import shutil
import time
import zipfile
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
import segmentation_models_pytorch as smp
import shapely
import torch
import torch.nn.functional as F
import yaml
from affine import Affine
from pyproj import CRS as PCRS
from rasterio import features
from rasterio.enums import Resampling
from rasterio.windows import from_bounds
from scipy import ndimage as ndi
from shapely.affinity import affine_transform
from shapely.geometry import LineString, Point, box
from shapely.ops import substring, unary_union
from skimage.graph import route_through_array

BANDS = (1, 2, 3)          # R, G, B band numbers in your GeoTIFFs
CACHE = Path(os.environ.get("CANAL_CACHE", "/content/cache"))   # fast local disk for downloads
DEFAULTS = dict(
    # data / labels
    res_m=0.5, buffer_m=80, core_m=3, near_m=12,
    # tracing
    corridor_m=40, retry_corridor_m=75, retry_prob=0.35, pull=0.15, wp_m=300, smooth_m=6, sigma_m=1.5,
    join_m=5, centre_m=15,
    # reaches / confidence
    reach_m=50, flag_prob=0.3,
    # line acceptance (Karnataka notebook): a traced line is a supported canal only if its mean
    # probability >= min_mean_prob AND >= min_coverage of its pixels reach pixel_prob_threshold.
    # Both are measured on the unsmoothed trace, so smoothing cannot create evidence.
    min_mean_prob=0.5, min_coverage=0.6, pixel_prob_threshold=0.5,
    # model / training
    encoder="efficientnet-b0", pretrained=True, tile=256, tiles_per_site=400, steps=1500, batch=16, lr=3e-4,
    scale_aug=0.2, color_aug=True, neg_m=4, neg_w=3, neg_share=0.3, val_frac=0.1, val_every=100, amp=True, cv_steps=None,
    # prediction
    tta=True,
)
DEV = "cuda" if torch.cuda.is_available() else "cpu"
MEAN = np.array([0.485, 0.456, 0.406], np.float32)[:, None, None]    # ImageNet stats (pretrained encoders)
STD = np.array([0.229, 0.224, 0.225], np.float32)[:, None, None]
rng = np.random.default_rng(0)
print = functools.partial(print, flush=True)      # show progress live (Colab buffers !python output)


# ------------------------------------------------------------------ getting data (Drive link or path)
def _check(src):
    if "PASTE" in str(src):
        raise SystemExit(f"Fill in the config first, still a placeholder: {src}")
    if not str(src).startswith("http") and not Path(src).exists():
        raise SystemExit(f"Not found: {src}")


def _download(url):
    """Download a Drive file/folder link once into the local cache; return its directory."""
    d = CACHE / hashlib.md5(url.encode()).hexdigest()[:10]
    if not (d / ".done").exists():
        import gdown
        d.mkdir(parents=True, exist_ok=True)
        print(f"downloading {url} ...")
        if "/folders/" in url:
            gdown.download_folder(url=url, output=str(d), quiet=True, use_cookies=False)
        else:
            m = re.search(r"/d/([\w-]+)|[?&]id=([\w-]+)", url)
            if not m:
                raise SystemExit(f"Can't find a Drive file id in: {url}")
            gdown.download(id=m.group(1) or m.group(2), output=str(d) + "/", quiet=True)
        if not any(f.name != ".done" for f in d.rglob("*") if f.is_file()):
            raise SystemExit(f"Download failed (link must be shared 'Anyone with the link'): {url}")
        (d / ".done").touch()
    return d


def fetch_raster(src):
    _check(src)
    if str(src).startswith("http"):
        f = next(iter(sorted(_download(src).rglob("*.tif*"))), None)
        if f is None:
            raise SystemExit(f"No .tif found at {src}")
        return f
    dst = CACHE / "copies" / Path(src).name          # Drive is slow to read from; copy once
    if not dst.exists() or dst.stat().st_size != Path(src).stat().st_size:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(src, dst)
    return dst


def fetch_shp(src):
    """Path to a .shp, a Drive folder link holding one, or a zip (path or link) of one."""
    _check(src)
    p = _download(src) if str(src).startswith("http") else Path(src)
    if p.suffix == ".zip":
        out = CACHE / "unzipped" / hashlib.md5(str(p).encode()).hexdigest()[:10]
        if not out.exists():
            shutil.unpack_archive(p, out)
        p = out
    if p.is_dir():
        found = sorted(p.rglob("*.shp"))
        if len(found) != 1:
            raise SystemExit(f"Need exactly one .shp in {src}, found {len(found)}")
        p = found[0]
    for ext in (".dbf", ".shx"):
        if not p.with_suffix(ext).exists():
            raise SystemExit(f"{p.name} is missing its {ext} file - give a folder link or a .zip, "
                             "a link to the .shp alone is not enough")
    return p


# ------------------------------------------------------------------ geometry
def pixel_m(src):
    """Pixel size in metres (projected CRS: as is; geographic: degrees -> metres at the image centre)."""
    if src.crs.is_projected:
        return src.res[0]
    lat = (src.bounds.top + src.bounds.bottom) / 2
    return src.res[0] * 111320 * np.cos(np.radians(lat))


def _m_to_crs(crs, m):
    """Metres -> units of `crs` (degrees for a geographic CRS, approximately)."""
    return m / 111320 if PCRS.from_user_input(crs).is_geographic else m


def read_rgb(src, window=None, out_shape=None):
    """RGB bands, with nodata / alpha / masked pixels set to 0 (so they are treated as 'no image')."""
    shape = None if out_shape is None else (len(BANDS), *out_shape)
    img = src.read(BANDS, window=window, out_shape=shape, resampling=Resampling.average)
    if src.nodata is not None or src.count > len(BANDS) or any(
            f != rasterio.enums.MaskFlags.all_valid for f in src.mask_flag_enums[0]):
        msk = src.dataset_mask(window=window, out_shape=out_shape)
        img[:, msk == 0] = 0
    return img


def load_small(path, res_m):
    """Read the (huge) raster decimated to ~res_m metres/pixel."""
    with rasterio.open(path) as src:
        px = pixel_m(src)
        f = max(1.0, res_m / px)
        h, w = int(src.height / f), int(src.width / f)
        img = read_rgb(src, None, (h, w))
        tr = src.transform * Affine.scale(src.width / w, src.height / h)
        return img, tr, src.crs, src.bounds, px * src.width / w


def load_canals(src, crs, bounds, src_crs=None, dx=0, dy=0):
    """Lines from a path or GeoDataFrame, shifted (dx, dy metres), reprojected to the raster CRS and
    clipped to its extent."""
    g = src if isinstance(src, gpd.GeoDataFrame) else gpd.read_file(src)
    if src_crs:                                    # wrong tag -> override, don't reproject
        g = g.set_crs(src_crs, allow_override=True)
    if g.crs is None:
        raise SystemExit("A shapefile has no CRS: set canals_crs in the config.")
    pad = _m_to_crs(crs, abs(dx) + abs(dy) + 1)    # lines just outside may be shifted in
    l, b, r, t = bounds
    bb = gpd.GeoSeries([box(l - pad, b - pad, r + pad, t + pad)], crs=crs).to_crs(g.crs).total_bounds
    g = g.cx[bb[0]:bb[2], bb[1]:bb[3]]
    if g.empty:
        return g.to_crs(crs)
    g = g.to_crs(crs)
    if dx or dy:                                   # constant offset in metres (east, north)
        g = g.to_crs(g.estimate_utm_crs())
        g = g.set_geometry(g.translate(dx, dy)).to_crs(crs)
    g = gpd.clip(g, box(*bounds)).explode(index_parts=False)
    g = g[g.geom_type == "LineString"]
    return g[g.length > 0].reset_index(drop=True)


def load_national(path, crs, bounds, src_crs=None, dx=0, dy=0, pad_m=100):
    """Read ONLY the all-India lines near the image (bbox read through the file's spatial index), then
    load_canals. Much faster and lighter than reading the whole country."""
    fcrs = src_crs or gpd.read_file(path, rows=1).crs
    if fcrs is None:
        raise SystemExit("The all-India shapefile has no CRS: set canals_crs in the config.")
    l, b, r, t = gpd.GeoSeries([box(*bounds)], crs=crs).to_crs(fcrs).total_bounds
    pad = _m_to_crs(fcrs, pad_m + abs(dx) + abs(dy))
    g = gpd.read_file(path, bbox=(l - pad, b - pad, r + pad, t + pad))
    if g.crs is None or src_crs:
        g = g.set_crs(fcrs, allow_override=True)
    return load_canals(g, crs, bounds, None, dx, dy)


def metric_buffer(g, crs, dist_m):
    """Buffer in local UTM so the distance is real metres; return in raster CRS."""
    buf = g.to_crs(g.estimate_utm_crs()).buffer(dist_m).to_crs(crs)
    return unary_union(buf.geometry.values)


def mask(geom, shape, tr=Affine.identity()):
    if geom.is_empty:
        return np.zeros(shape, bool)
    return features.rasterize([geom], out_shape=shape, transform=tr, fill=0, default_value=1,
                              all_touched=True, dtype="uint8").view(bool)      # view: no extra copy


def px_to_crs(geom, tr):
    """Pixel-space geometry (x = column, y = row, continuous) -> raster CRS."""
    return affine_transform(geom, [tr.a, tr.b, tr.d, tr.e, tr.c, tr.f])


# ------------------------------------------------------------------ model: pretrained U-Net
def img_scale(img):
    vals = img[img > 0]
    return float(np.percentile(vals[::97], 99)) if vals.size else 255.0


def prep(img, scale):
    return (np.clip(img.astype(np.float32) / scale, 0, 1) - MEAN) / STD


def build_model(encoder, pretrained):
    return smp.Unet(encoder, encoder_weights="imagenet" if pretrained else None,
                    in_channels=3, classes=1).to(DEV)


def load_model(path):
    M = torch.load(path, map_location=DEV, weights_only=False)
    if tuple(M["bands"]) != BANDS:
        raise SystemExit(f"Model was trained on bands {M['bands']}, script uses {BANDS}")
    model = build_model(M["encoder"], False)
    model.load_state_dict(M["state"])
    model.eval()
    return model, M


def scale_of(path):
    """Brightness scale for an image (same in train and predict): 99th percentile at ~2 m/px."""
    return img_scale(load_small(path, 2.0)[0])


def _amp(enabled):
    return torch.autocast("cuda", dtype=torch.float16, enabled=enabled and DEV == "cuda")


def seg_loss(out, y, w):
    """Masked BCE + Dice (dice: canal is a thin, rare class). Pixels with w = 0 are ignored."""
    bce = (F.binary_cross_entropy_with_logits(out, y, reduction="none") * w).sum() / w.sum().clamp(min=1)
    s = torch.sigmoid(out) * w
    dice = 1 - (2 * (s * y).sum() + 1) / (s.sum() + y.sum() + 1)
    return bce + dice


def color_jitter(x):
    """Random brightness / contrast / colour balance on normalised tiles (seasons, drones, exposure)."""
    n = x.shape[0]
    mean = torch.tensor(MEAN, device=x.device)
    std = torch.tensor(STD, device=x.device)
    u = x * std + mean                                                   # back to 0-1
    bright = torch.empty(n, 1, 1, 1, device=x.device).uniform_(0.75, 1.25)
    contrast = torch.empty(n, 1, 1, 1, device=x.device).uniform_(0.8, 1.2)
    gain = torch.empty(n, 3, 1, 1, device=x.device).uniform_(0.92, 1.08)
    m = u.mean((1, 2, 3), keepdim=True)
    u = ((u - m) * contrast + m) * bright * gain
    return (u.clamp(0, 1) - mean) / std


# ------------------------------------------------------------------ training data
def _val_block(x, y, blk, k):
    """Deterministic spatial split: tiles whose centre falls in every k-th block are validation."""
    if not k:
        return False
    bx, by = int(np.floor(x / blk)), int(np.floor(y / blk))
    return (abs(bx * 73856093 ^ by * 19349663) % k) == 0


def site_tiles(tif, gt, P, n, core_m, near_m, neg=None):
    """n random TxT crops around the truth lines, read window by window straight from the GeoTIFF
    (never the whole image, so any size / resolution works) -> (image, canal label, loss weight, is_val).
    Each tile covers T * res_m metres times a random scale (scale_aug), so the model sees canals at
    slightly different pixel sizes and copes with other drones / flying heights.
    `neg` (optional): lines of things that look like a canal but are not (roads, bunds, field tracks).
    Pixels within neg_m of them are labelled NOT canal with neg_w times the weight, even far from the
    truth, and neg_share of the tiles are centred on them, so the model learns road != canal."""
    T = P["tile"]
    scale = scale_of(tif)
    X, Y, M, V = [], [], [], []
    with rasterio.open(tif) as src:
        crs = src.crs
        unit = 1.0 if crs.is_projected else 1 / 111320
        half0 = T * P["res_m"] * unit / 2                                       # half a tile, CRS units
        l, b, r, t = src.bounds
        if r - l < 2 * half0 * (1 + P["scale_aug"]) or t - b < 2 * half0 * (1 + P["scale_aug"]):
            return None
        canal, near, zone = (metric_buffer(gt, crs, d) for d in (core_m, near_m, P["buffer_m"]))
        lines = list(gt.geometry)
        p = np.array([ln.length for ln in lines]); p /= p.sum()
        has_neg = neg is not None and not neg.empty
        if has_neg:
            negbuf = metric_buffer(neg, crs, P["neg_m"])
            nlines = list(neg.geometry)
            pn = np.array([ln.length for ln in nlines]); pn /= pn.sum()
        blk = 4 * half0                                                          # validation block = 2 tiles
        k = int(round(1 / P["val_frac"])) if P["val_frac"] else 0
        for _ in range(n * 5):
            if len(X) == n:
                break
            half = half0 * (1 + rng.uniform(-P["scale_aug"], P["scale_aug"]))
            if has_neg and rng.random() < P["neg_share"]:
                q = nlines[rng.choice(len(nlines), p=pn)].interpolate(rng.random(), normalized=True)
            else:
                q = lines[rng.choice(len(lines), p=p)].interpolate(rng.random(), normalized=True)
            x = np.clip(q.x + rng.normal(0, half / 2), l + half, r - half)        # jitter: canal not always centred
            y = np.clip(q.y + rng.normal(0, half / 2), b + half, t - half)
            win = from_bounds(x - half, y - half, x + half, y + half, src.transform)
            img = read_rgb(src, win, (T, T))
            valid = img.max(0) > 0
            if valid.mean() < 0.5:                                                 # mostly no-image background
                continue
            tr = rasterio.windows.transform(win, src.transform) * Affine.scale(win.width / T, win.height / T)
            tile = box(x - half, y - half, x + half, y + half)
            c, nr, z = (mask(g.intersection(tile), (T, T), tr) for g in (canal, near, zone))
            keep = (c | (z & ~nr)) & valid                                         # ring between core and near_m ignored
            wgt = keep.astype(np.uint8)
            if has_neg:
                ng = mask(negbuf.intersection(tile), (T, T), tr) & ~c & valid      # hard negatives: road, bund...
                keep |= ng
                wgt = keep.astype(np.uint8) + ng.astype(np.uint8) * (P["neg_w"] - 1)
            X.append(prep(img, scale).astype(np.float16)); Y.append((c & keep)[None]); M.append(wgt[None])
            V.append(_val_block(x, y, blk, k))
            if len(X) % 100 == 0:
                print(f"   {len(X)}/{n} tiles")
    if not X:
        return None
    return np.stack(X), np.stack(Y).astype(np.uint8), np.stack(M).astype(np.uint8), np.array(V, bool)


def cut_site(t, P):
    """Training tiles for one config site, or None (with the reason printed)."""
    tif = fetch_raster(t["image"])
    with rasterio.open(tif) as src:
        gt = load_canals(fetch_shp(t["truth"]), src.crs, src.bounds, t.get("truth_crs"))
        neg = (load_canals(fetch_shp(t["negatives"]), src.crs, src.bounds, t.get("truth_crs"))
               if t.get("negatives") else None)
    core, near = t.get("core_m", P["core_m"]), t.get("near_m", P["near_m"])
    got = None if gt.empty else site_tiles(tif, gt, P, P["tiles_per_site"], core, near, neg)
    if got is None:
        print(f"[{t['name']}] SKIPPED: no truth lines overlap this image (check CRS), or image smaller than a tile")
        return None
    print(f"[{t['name']}] {len(gt)} truth segments, {len(got[0])} tiles ({got[3].sum()} validation), "
          f"canal label {core} m / ignore to {near} m"
          + (f", {len(neg)} 'not canal' lines (roads, bunds)" if neg is not None and len(neg) else ""))
    return got


def _concat(parts):
    return tuple(np.concatenate([p[i] for p in parts]) for i in range(4))


# ------------------------------------------------------------------ training
@torch.no_grad()
def validate(model, X, Y, M, P):
    """Validation loss and canal IoU (threshold 0.5, ignored pixels excluded)."""
    model.eval()
    loss, inter, union, nb = 0.0, 0.0, 0.0, 0
    for i in range(0, len(X), P["batch"]):
        x, y, w = (torch.from_numpy(a[i:i + P["batch"]].astype(np.float32)).to(DEV) for a in (X, Y, M))
        with _amp(P["amp"]):
            out = model(x)
        out = out.float()
        loss += seg_loss(out, y, w).item(); nb += 1
        wb = (w > 0).float()
        pr = (out > 0).float() * wb
        inter += (pr * y).sum().item(); union += ((pr + y) > 0).float().mul(wb).sum().item()
    model.train()
    return loss / max(nb, 1), inter / max(union, 1)


def train_model(P, data, steps, model_path):
    """Fine-tune on (X, Y, M, V); keep the checkpoint with the best validation IoU."""
    X, Y, M, V = data
    has_val = V.sum() >= 4 and (~V).sum() >= P["batch"]
    Xt, Yt, Mt = (a[~V] for a in (X, Y, M)) if has_val else (X, Y, M)
    Xv, Yv, Mv = (a[V] for a in (X, Y, M)) if has_val else (None, None, None)
    torch.manual_seed(0)                                        # reproducible runs
    model = build_model(P["encoder"], P["pretrained"])
    opt = torch.optim.AdamW(model.parameters(), P["lr"])
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=P["lr"], total_steps=steps, pct_start=0.1)
    use_amp = P["amp"] and DEV == "cuda"
    try:
        scaler = torch.amp.GradScaler("cuda", enabled=use_amp)
    except (AttributeError, TypeError):
        scaler = torch.cuda.amp.GradScaler(enabled=use_amp)
    print(f"training on {DEV}, {len(Xt)} tiles" + (f", validating on {len(Xv)}" if has_val else ", no validation split")
          + ("  <-- VERY SLOW: Runtime > Change runtime type > GPU" if DEV == "cpu" else ""))
    model_path = Path(model_path)
    model_path.parent.mkdir(parents=True, exist_ok=True)
    meta = {"encoder": P["encoder"], "res_m": P["res_m"], "tile": P["tile"], "bands": list(BANDS)}
    best, t0 = -1.0, time.time()
    for step in range(steps):
        i = rng.integers(0, len(Xt), P["batch"])
        x, y, w = (torch.from_numpy(a[i].astype(np.float32)) for a in (Xt, Yt, Mt))
        k = int(rng.integers(4))                                # random rotate / flip augmentation
        x, y, w = (torch.rot90(a, k, (2, 3)) for a in (x, y, w))
        if rng.random() < 0.5:
            x, y, w = (torch.flip(a, (3,)) for a in (x, y, w))
        x, y, w = x.to(DEV), y.to(DEV), w.to(DEV)
        if P["color_aug"]:
            x = color_jitter(x)
        with _amp(use_amp):
            out = model(x)
        loss = seg_loss(out.float(), y, w)
        opt.zero_grad()
        scaler.scale(loss).backward(); scaler.step(opt); scaler.update(); sched.step()
        last = step == steps - 1
        if step % P["val_every"] == 0 or last:
            msg = f"step {step}/{steps} loss {loss.item():.3f}"
            if has_val:
                vl, iou = validate(model, Xv, Yv, Mv, P)
                msg += f" | val loss {vl:.3f} IoU {iou:.3f}"
                if iou > best:
                    best = iou
                    torch.save({"state": model.state_dict(), **meta, "val_iou": float(iou), "step": step}, model_path)
                    msg += "  *saved"
            print(msg + f"  ({(time.time() - t0) / (step + 1):.2f} s/step)")
    if not has_val:
        torch.save({"state": model.state_dict(), **meta, "val_iou": None, "step": steps - 1}, model_path)
    print(f"-> {model_path}" + (f" (best validation IoU {best:.3f})" if has_val else ""))
    return best if has_val else None


def setup(cfg):
    P = {**DEFAULTS, **(cfg.get("params") or {})}
    assert P["tile"] % 32 == 0, "tile must be a multiple of 32"
    if P["buffer_m"] < P["corridor_m"]:
        print(f"note: buffer_m ({P['buffer_m']}) < corridor_m ({P['corridor_m']}): the trace cannot use "
              "evidence outside the buffer; set buffer_m >= corridor_m")
    if P["retry_corridor_m"] and P["retry_corridor_m"] > P["buffer_m"]:
        P["retry_corridor_m"] = P["buffer_m"]
    work = Path(cfg["work_dir"])
    work.mkdir(parents=True, exist_ok=True)
    return P, work


def train(cfg):
    P, work = setup(cfg)
    parts = [d for d in (cut_site(t, P) for t in cfg["train"]) if d is not None]
    if not parts:
        raise SystemExit("No training data.")
    train_model(P, _concat(parts), P["steps"], work / "model.pt")


# ------------------------------------------------------------------ prediction
@torch.no_grad()
def predict_prob(img, model, inbuf, T, scale, batch=16, tta=True, amp=True):
    """Sliding-window canal probability (uint8 0-255), only where the buffer is and the image is not black.
    Tiles overlap and each writes only its centre (edges are the least reliable). Tiles run in batches;
    with tta, each tile is also predicted flipped three ways and the four results averaged."""
    H, W = img.shape[1:]
    m = T // 8
    prob = np.zeros((H, W), np.uint8)
    rows = list(range(0, max(H - T, 0), T - 2 * m)) + [max(H - T, 0)]
    cols = list(range(0, max(W - T, 0), T - 2 * m)) + [max(W - T, 0)]
    jobs = [(r, c) for r in rows for c in cols if inbuf[r:r + T, c:c + T].any()]
    flips = [(), (3,), (2,), (2, 3)] if tta else [()]
    for k in range(0, len(jobs), batch):
        chunk = jobs[k:k + batch]
        raws = [img[:, r:r + T, c:c + T] for r, c in chunk]
        t = np.stack([prep(np.pad(raw, ((0, 0), (0, T - raw.shape[1]), (0, T - raw.shape[2]))), scale)
                      for raw in raws])
        x = torch.from_numpy(t).to(DEV)
        pr = 0
        with _amp(amp):
            for f in flips:
                o = torch.sigmoid(model(x.flip(f) if f else x).float())
                pr = pr + (o.flip(f) if f else o)
        pr = (pr / len(flips))[:, 0].cpu().numpy()
        for (r, c), raw, p in zip(chunk, raws, pr):
            h, w = raw.shape[1:]
            p = p[:h, :w] * inbuf[r:r + h, c:c + w] * (raw.max(0) > 0)
            r0, r1 = r + (m if r > 0 else 0), r + h - (m if r + T < H else 0)    # keep the centre, except at image edges
            c0, c1 = c + (m if c > 0 else 0), c + w - (m if c + T < W else 0)
            prob[r0:r1, c0:c1] = (p[r0 - r:r1 - r, c0 - c:c1 - c] * 255).astype(np.uint8)
    return prob


# ------------------------------------------------------------------ line tracing
def snap(prob, r, c, rad, thr=100):
    """Move a waypoint to the strongest nearby ridge, preferring ridges close to the original
    point. If nothing convincing is nearby, keep the point where it is. Returns (r, c, found)."""
    H, W = prob.shape
    r, c = min(max(r, 0), H - 1), min(max(c, 0), W - 1)
    r0, c0 = max(r - rad, 0), max(c - rad, 0)
    r1, c1 = min(r + rad + 1, H), min(c + rad + 1, W)
    win = ndi.uniform_filter(prob[r0:r1, c0:c1].astype(np.float32), 5)
    if win.max() < thr:
        return r, c, False
    rr, cc = np.mgrid[r0:r1, c0:c1]
    score = win * np.exp(-(((rr - r) ** 2 + (cc - c) ** 2) / (0.6 * rad) ** 2))
    i, j = np.unravel_index(np.argmax(score), score.shape)
    return r0 + i, c0 + j, True


def translate_line(ln, dx, dy):
    return LineString([(x + dx, y + dy) for x, y in ln.coords])


def _segment(lp, prob, a, b, pad, sigma_px, pull):
    """Least-cost path from cell a to cell b inside a corridor of `pad` px around the original line."""
    H, W = prob.shape
    r0, r1 = max(min(a[0], b[0]) - pad, 0), min(max(a[0], b[0]) + pad + 1, H)
    c0, c1 = max(min(a[1], b[1]) - pad, 0), min(max(a[1], b[1]) + pad + 1, W)
    sub = ndi.gaussian_filter(prob[r0:r1, c0:c1].astype(np.float32) / 255, sigma_px)
    line = features.rasterize([translate_line(lp, -c0, -r0)], out_shape=sub.shape,
                              fill=0, default_value=1, all_touched=True)
    d = ndi.distance_transform_edt(line == 0) if line.any() else np.full(sub.shape, 1e3)
    cost = (1 - sub) ** 2 + 0.01 + pull * (d / pad) ** 2
    cost[d > pad * 1.2] = 1e3
    cost[a[0] - r0, a[1] - c0] = cost[b[0] - r0, b[1] - c0] = 0.01          # end points always reachable
    idx, _ = route_through_array(cost, (a[0] - r0, a[1] - c0), (b[0] - r0, b[1] - c0),
                                 fully_connected=True, geometric=True)
    return [(r + r0, c + c0) for r, c in idx]


def path_prob(prob, path):
    a = np.asarray(path, int)
    return float(prob[a[:, 0], a[:, 1]].mean()) / 255


def path_coverage(prob, path, thr):
    """Share (0-1) of traced cells whose canal probability reaches thr (0-1)."""
    a = np.asarray(path, int)
    if not len(a):
        return 0.0
    return float((prob[a[:, 0], a[:, 1]] >= thr * 255).mean())


def route(lp, prob, res_m, P, sigma_px):
    """Least-cost path along the (smoothed) probability, inside a corridor around the original line,
    with a soft pull towards the original line where the image gives no evidence.
    Adaptive corridor: waypoints that find no canal within corridor_m search again out to
    retry_corridor_m, and a stretch between two waypoints whose path finds little canal (mean
    probability < retry_prob) is re-routed in the wider corridor (kept only if clearly better).
    Returns (path cells, mean probability, widest corridor used in m)."""
    pad = max(int(P["corridor_m"] / res_m), 3)
    pad2 = max(int((P["retry_corridor_m"] or 0) / res_m), pad)
    n = max(2, int(lp.length * res_m / P["wp_m"]) + 1)
    pts = []
    for i in range(n):
        q = lp.interpolate(i / (n - 1), normalized=True)
        r, c, found = snap(prob, int(q.y), int(q.x), pad)
        if not found and pad2 > pad:
            r, c, _ = snap(prob, int(q.y), int(q.x), pad2)
        pts.append((r, c))
    path, used = [], pad
    for a, b in zip(pts[:-1], pts[1:]):
        # the corridor must at least contain both (possibly far-snapped) end points
        need = max(Point(a[1] + .5, a[0] + .5).distance(lp), Point(b[1] + .5, b[0] + .5).distance(lp))
        p0 = min(max(pad, int(need / 1.1) + 2), pad2)
        seg = _segment(lp, prob, a, b, p0, sigma_px, P["pull"])
        if pad2 > p0 and path_prob(prob, seg) < P["retry_prob"]:
            seg2 = _segment(lp, prob, a, b, pad2, sigma_px, P["pull"])
            if path_prob(prob, seg2) > path_prob(prob, seg) + 0.1:
                seg, p0 = seg2, pad2
        used = max(used, p0)
        path += seg
    return path, path_prob(prob, path), round(used * res_m)


def smooth(path, sigma_px):
    p = np.array(path, float)
    p = p[np.r_[True, (np.diff(p, axis=0) != 0).any(1)]]     # drop duplicate junction points
    if len(p) > 3 and sigma_px > 0:
        s = ndi.gaussian_filter1d(p, sigma_px, axis=0, mode="nearest")
        s[0], s[-1] = p[0], p[-1]
        p = s
    return p


def recentre(line, prob, res, half_m, sigma_px, step_px=2.0):
    """Move the traced line to the CENTRE of the canal band. The model is only penalised beyond near_m,
    so its canal band is wider than the canal centre, and the least-cost path, pulled towards the
    all-India line, tends to run along the band edge nearest to it (a 1-3 m bias). For points every
    step_px along the line, look across the line (+- half_m), find the run of probability >= 0.5
    under (or nearest to) the point and move the point to the middle of that run. Shifts are smoothed
    along the line; where there is no canal evidence (e.g. a vegetated stretch) neighbours' shifts carry over."""
    if half_m <= 0 or line.length < 4 * step_px:
        return line
    P = shapely.get_coordinates(shapely.line_interpolate_point(line, np.arange(0, line.length, step_px)))
    P = np.vstack([P, line.coords[-1]])
    tg = np.gradient(ndi.gaussian_filter1d(P, 3, axis=0, mode="nearest"), axis=0)
    tg /= np.linalg.norm(tg, axis=1, keepdims=True).clip(1e-9)
    nv = np.stack([-tg[:, 1], tg[:, 0]], 1)                                  # unit normal (x, y)
    offs = np.arange(-half_m / res, half_m / res + 1e-9, 0.5)
    S = P[:, None, :] + offs[None, :, None] * nv[:, None, :]
    vals = ndi.map_coordinates(prob, [S[..., 1].ravel() - 0.5, S[..., 0].ravel() - 0.5], order=1,
                               mode="constant").reshape(S.shape[:2])
    above = ndi.binary_closing(vals >= 128, structure=np.ones((1, 5)))      # bridge 1-2 px gaps
    c0 = len(offs) // 2
    shift, ok = np.zeros(len(P)), np.zeros(len(P))
    for i, row in enumerate(above):
        if not row.any():
            continue
        lab, n = ndi.label(row)
        if lab[c0]:
            k = lab[c0]
        else:                                                               # nearest run to the point
            idx = np.flatnonzero(row)
            k = lab[idx[np.argmin(np.abs(idx - c0))]]
        run = np.flatnonzero(lab == k)
        shift[i], ok[i] = (offs[run[0]] + offs[run[-1]]) / 2, 1
    sg = max(sigma_px / step_px, 1)
    w = ndi.gaussian_filter1d(ok, sg, mode="nearest")
    s = np.where(w > 0.2, ndi.gaussian_filter1d(shift * ok, sg, mode="nearest") / w.clip(1e-9), 0)
    return LineString(P + s[:, None] * nv)


def join_junctions(orig, traced, tol_px, max_px):
    """Where an original line ENDS on another original line (a junction, or two pieces of one canal),
    extend the traced end onto the other traced line, so the output network stays connected."""
    out = []
    for i, (o, t) in enumerate(zip(orig, traced)):
        coords = list(t.coords)
        for end in (0, -1):
            e = Point(o.coords[end])
            best = None
            for j, o2 in enumerate(orig):
                if j != i:
                    d = o2.distance(e)
                    if d <= tol_px and (best is None or d < best[0]):
                        best = (d, j)
            if best is None:
                continue
            tj = traced[best[1]]
            p = Point(coords[end])
            q = tj.interpolate(tj.project(p))
            if 0.5 < p.distance(q) <= max_px:
                if end == 0:
                    coords.insert(0, (q.x, q.y))
                else:
                    coords.append((q.x, q.y))
        out.append(LineString(coords))
    return out


def reaches(line, probq, res, reach_m):
    """Cut a pixel-space line into reach_m pieces -> [(chainage m, piece, confidence 0-1)].
    Confidence = mean canal probability sampled every pixel along the piece."""
    H, W = probq.shape
    L, step = line.length, reach_m / res
    out = []
    for k in range(max(1, int(np.ceil(L / step - 1e-9)))):
        seg = substring(line, k * step, min((k + 1) * step, L))
        if seg.geom_type != "LineString" or seg.length == 0:
            continue
        pts = shapely.get_coordinates(shapely.line_interpolate_point(seg, np.arange(0, seg.length + 1e-9, 1.0)))
        rr = np.clip(pts[:, 1].astype(int), 0, H - 1)
        cc = np.clip(pts[:, 0].astype(int), 0, W - 1)
        out.append((k * reach_m, seg, float(probq[rr, cc].mean()) / 255))
    return out


def evaluate(truth, lines, step=5):
    """How far (m) is the ground truth from the nearest line in `lines`? Points every `step` m."""
    if lines.empty:
        return None
    utm = truth.estimate_utm_crs()
    u = unary_union(lines.to_crs(utm).geometry.values)
    d = []
    for ln in truth.to_crs(utm).geometry:
        n = max(int(ln.length // step), 1)
        pts = shapely.line_interpolate_point(ln, np.linspace(0, ln.length, n + 1))
        d += list(shapely.distance(pts, u))
    d = np.array(d)
    return dict(mean=float(d.mean()), p90=float(np.percentile(d, 90)),
                w2=float((d <= 2).mean() * 100), w5=float((d <= 5).mean() * 100))


def fmt(e):
    if e is None:
        return "no lines"
    return (f"mean {e['mean']:.1f} m | p90 {e['p90']:.1f} m | within 2 m: {e['w2']:.0f} per cent | "
            f"within 5 m: {e['w5']:.0f} per cent")


def refine_lines(img, tr, crs, res, g, model, MD, P, scale, progress=None):
    """Core of predict, shared with the blockage app: canal probability inside the buffer around the lines
    `g` (raster CRS), trace + re-centre + join every line, cut into reaches with a confidence score.
    Returns (lines GeoDataFrame, reaches GeoDataFrame, probability uint8 array, (seconds prob, seconds trace))."""
    t0 = time.time()
    H, W = img.shape[1:]
    inbuf = mask(metric_buffer(g, crs, P["buffer_m"]), (H, W), tr)
    prob = predict_prob(img, model, inbuf, MD["tile"], scale, P["batch"], P["tta"], P["amp"])
    del inbuf
    t1 = time.time()
    if progress:
        progress("tracing")

    inv, sig = ~tr, P["sigma_m"] / res
    origs, traced, info = [], [], []
    for _, row in g.iterrows():
        lp = LineString([inv * (x, y) for x, y in row.geometry.coords])
        path, mp, corr = route(lp, prob, res, P, sig)
        cov = path_coverage(prob, path, P["pixel_prob_threshold"])
        sm = smooth(path, P["smooth_m"] / res)
        line = LineString(sm[:, ::-1] + 0.5) if len(sm) >= 2 else lp       # (row, col) cell -> (x, y) centre
        line = recentre(line, prob, res, P["centre_m"], P["smooth_m"] / res)
        origs.append(lp); traced.append(line); info.append((row, mp, cov, corr))
    traced = join_junctions(origs, traced, P["join_m"] / res, P["corridor_m"] / res)

    probq = ndi.maximum_filter(prob, 5)          # confidence: tolerate a 1-2 px offset from the ridge
    lines, rch = [], []
    for k, (lp, line, (row, mp, cov, corr)) in enumerate(zip(origs, traced, info)):
        attrs = row.drop("geometry").to_dict()
        rs = reaches(line, probq, res, P["reach_m"])
        pts = shapely.line_interpolate_point(line, np.arange(0, line.length + 1e-9, max(5 / res, 1)))
        shift = float(np.mean(shapely.distance(pts, lp))) * res
        nchk = sum(c < P["flag_prob"] for _, _, c in rs)
        lines.append({**attrs, "line_id": k, "mean_prob": round(mp, 3), "coverage": round(cov, 3),
                      "accepted": bool(mp >= P["min_mean_prob"] and cov >= P["min_coverage"]), "shift_m": round(shift, 1),
                      "corr_m": corr, "n_reach": len(rs), "n_check": nchk,
                      "geometry": px_to_crs(line.simplify(1.0), tr)})
        for ch, seg, conf in rs:
            rch.append({**attrs, "line_id": k, "chain_m": ch, "conf": round(conf, 3),
                        "status": "check" if conf < P["flag_prob"] else "ok", "geometry": px_to_crs(seg, tr)})
    out = gpd.GeoDataFrame(lines, crs=crs)
    out_r = gpd.GeoDataFrame(rch, crs=crs)
    return out, out_r, prob, (t1 - t0, time.time() - t1)


def predict(cfg, image, truth=None, name=None, model_path=None, out_dir=None):
    """Trace the all-India lines on one image. Returns a small dict of results (and metrics if truth)."""
    P, work = setup(cfg)
    model, MD = load_model(model_path or work / "model.pt")
    if MD["res_m"] != P["res_m"]:
        print(f"note: using res_m={MD['res_m']} (the model's), not {P['res_m']}")
    pc = cfg["predict"]
    tif = fetch_raster(image)
    name = name or tif.stem
    out_dir = Path(out_dir or work / "out")
    out_dir.mkdir(parents=True, exist_ok=True)

    img, tr, crs, bounds, res = load_small(tif, MD["res_m"])
    g = load_national(fetch_shp(pc["canals"]), crs, bounds, pc.get("canals_crs"), pc.get("dx", 0), pc.get("dy", 0))
    if g.empty:
        print(f"[{name}] SKIPPED: no canal lines overlap this image (check CRS)")
        return None
    H, W = img.shape[1:]
    print(f"[{name}] {W}x{H} px at {res:.2f} m, {len(g)} all-India segments")
    out, out_r, prob, (t_prob, t_trace) = refine_lines(img, tr, crs, res, g, model, MD, P, scale_of(tif))
    del img

    shp = out_dir / f"{name}.shp"
    out.to_file(shp)
    out_r.to_file(out_dir / f"{name}_reaches.shp")
    with rasterio.open(out_dir / f"{name}_prob.tif", "w", driver="GTiff", height=H, width=W, count=1,
                       dtype="uint8", crs=crs, transform=tr, compress="lzw", tiled=True) as dst:
        dst.write(prob, 1)
    with zipfile.ZipFile(out_dir / f"{name}.zip", "w", zipfile.ZIP_DEFLATED) as z:   # ready for the app upload
        for f in sorted(out_dir.glob(f"{name}.*")):
            if f.suffix in (".shp", ".shx", ".dbf", ".prj", ".cpg"):
                z.write(f, f.name)

    nacc = int(out["accepted"].sum())
    print(f"[{name}] accepted {nacc} of {len(out)} traced lines (mean_prob >= {P['min_mean_prob']}, "
          f"coverage >= {P['min_coverage']} at pixel probability {P['pixel_prob_threshold']}); "
          "rejected lines stay in the output with accepted=0 and must not be used as canal reaches")
    nchk = int((out_r["status"] == "check").sum()) if len(out_r) else 0
    retried = int((out["corr_m"] > P["corridor_m"]).sum())
    print(f"[{name}] {len(out)} lines, {len(out_r)} reaches of {P['reach_m']} m, {nchk} flagged 'check' "
          f"(confidence < {P['flag_prob']}), {retried} lines needed the wider corridor | "
          f"mean shift from the all-India line {out['shift_m'].mean():.1f} m | "
          f"probability {t_prob:.0f} s, tracing {t_trace:.0f} s")
    print(f"   -> {shp}  (+ _reaches.shp, _prob.tif, .zip)")
    result = dict(name=name, lines=len(out), reaches=len(out_r), flagged=nchk,
                  shift_m=round(float(out["shift_m"].mean()), 1))
    if truth:
        gt = load_canals(fetch_shp(truth), crs, bounds)
        if gt.empty:
            print("   truth does not overlap this image (check its CRS)")
        else:
            e0, e1 = evaluate(gt, g), evaluate(gt, out)
            print(f"   distance to ground truth, original lines: {fmt(e0)}")
            print(f"   distance to ground truth, model output  : {fmt(e1)}")
            result.update({f"orig_{k}": round(v, 1) for k, v in (e0 or {}).items()})
            result.update({f"model_{k}": round(v, 1) for k, v in (e1 or {}).items()})
    return result


# ------------------------------------------------------------------ leave-one-site-out
def cv(cfg):
    """Honest accuracy on unseen sites: for each site, train on all the others and test on it."""
    P, work = setup(cfg)
    sites = cfg["train"]
    if len(sites) < 2:
        raise SystemExit("cv needs at least two training sites")
    data = {t["name"]: cut_site(t, P) for t in sites}        # cut tiles once, reuse in every fold
    steps = P["cv_steps"] or P["steps"]
    rows = []
    for t in sites:
        others = [data[s["name"]] for s in sites if s["name"] != t["name"] and data[s["name"]] is not None]
        if data[t["name"]] is None or not others:
            continue
        print(f"\n===== fold: test on {t['name']}, train on the other {len(others)} site(s), {steps} steps =====")
        fold = work / "cv" / t["name"]
        iou = train_model(P, _concat(others), steps, fold / "model.pt")
        r = predict(cfg, t["image"], t["truth"], t["name"], fold / "model.pt", fold)
        rows.append({"site": t["name"], "val_iou": None if iou is None else round(iou, 3),
                     **(r or {"lines": 0})})
    if not rows:
        raise SystemExit("No fold could run.")
    keys = list(dict.fromkeys(k for r in rows for k in r))
    with open(work / "cv" / "cv_results.csv", "w", newline="") as f:
        w = csv.DictWriter(f, keys); w.writeheader(); w.writerows(rows)
    print("\n===== leave-one-site-out summary (distances in m, 'w2'/'w5' = per cent of truth within 2 / 5 m) =====")
    show = ["site", "orig_mean", "model_mean", "orig_w2", "model_w2", "orig_w5", "model_w5", "flagged"]
    print("  ".join(f"{k:>11}" for k in show))
    for r in rows:
        print("  ".join(f"{str(r.get(k, '-')):>11}" for k in show))
    print(f"-> {work / 'cv' / 'cv_results.csv'}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["train", "predict", "cv"])
    ap.add_argument("--config", required=True)
    ap.add_argument("--image", help="predict: the test image to trace (Drive link or path)")
    ap.add_argument("--truth", help="predict: optional ground-truth shapefile of that image (accuracy check)")
    ap.add_argument("--name", help="predict: output name (default: image file name)")
    a = ap.parse_args()
    cfg = yaml.safe_load(open(a.config))
    if a.cmd == "train":
        train(cfg)
    elif a.cmd == "cv":
        cv(cfg)
    elif a.image:
        predict(cfg, a.image, a.truth, a.name)
    else:
        ap.error("predict needs --image")
