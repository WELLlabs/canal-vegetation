# Phase 1.5 — Real data validation

## Verdict

**READY WITH KNOWN LIMITATIONS**

This is not a ground-truth accuracy evaluation. No notebook-07 saved masks/npz were available to compare pixel-for-pixel.

## Environment

| Item | Value |
|------|--------|
| OS | Windows 10 (10.0.26200) |
| Python | 3.13.14 (`backend/.venv`) |
| torch | 2.13.0+cpu |
| CUDA | **False** (CPU only) |
| rasterio | 1.5.1 |
| Device used | `cpu` |
| Peak memory | **not measured** |

## Asset table

| Asset | Exists | Path | Usable for test | Notes |
|-------|--------|------|-----------------|-------|
| ATTANUR_1 ortho | Yes | `D:\Github\Canal Pipeline\TLBC_D95_ATTANUR_1_ortho.tif` | Yes (large) | 4.16 GB; 32432×51991; 4-band; EPSG:32643; ~0.0462 m; ~11340 tiles |
| ATTANUR_2 ortho | Yes | `D:\Github\Canal Pipeline\TLBC_D95_ATTANUR_2_ortho.tif` | Yes (very large) | 22.5 GB; 179 alignment vertices in bounds |
| ATTANUR_3 ortho | Yes | `D:\Github\Canal Pipeline\TLBC_D95_ATTANUR_3_ortho.tif` | Yes (very large) | 17.7 GB; 97 alignment vertices |
| ATTANUR_4 ortho | Yes | `D:\Github\Canal Pipeline\TLBC_D95_ATTANUR_4_ortho.tif` | Yes | **Smallest file** 2.90 GB; **17702×43763**; 4-band uint8; EPSG:32643; **0.03518 m/px**; ~**5085** tiles; **0** TLBC_D95 vertices in bounds |
| SHAKAPUR ortho | Yes | `D:\Github\Canal Pipeline\TLBC_D95_SHAKAPUR_ortho.tif` | Yes | 10.3 GB; 88528×41855; 0.03425 m; 38 alignment vertices |
| Weights `_v5.pth` (product) | Yes | `backend\app\models\model_weights\best_binary_unet_v5.pth` | Yes | 124.4 MB; **selected** |
| Weights `_v5.pth` (reference) | Yes | `Canal Pipeline\TLBC_DSM_DTM\outputs\05b_binary\best_binary_unet_v5.pth` | Yes | 130436255 bytes |
| Weights `_lines.pth` | **No** | expected under `05b_binary` and `model_weights` | No | Notebook 07 Cell 1 prefers this file |
| Alignment shapefile | Yes | `Canal Pipeline\gis\TLBC_D95\TLBC_D95.shp` (+ `.shx` `.dbf` `.prj`) | Yes | 2 polylines; WGS84 `.prj`; intersects ATTANUR_2/3 and SHAKAPUR, **not** ATTANUR_1/4 |
| Production GeoJSON | Yes | `Canal Pipeline\production\attanur\boxes.geojson` | Compare-only | 191 features; GIS packaging, not UNet output |
| Production thumbnails | Yes | `Canal Pipeline\production\attanur\images\*.jpg` | Compare-only | Field/GIS boxes |
| Notebook 07 masks/npz | No | `TLBC_DSM_DTM\outputs\07_blockage*` | No | Directories empty / missing |

Real orthomosaics **exist**. Full-mosaic ATTANUR_4 on this CPU is estimated **~11 hours** (5085 tiles × ~8 s/tile from the 4096 window). That full file was **not** run to completion. Validation used **georeferenced windows of those real GeoTIFFs**.

## What was run

### 1. ATTANUR_4 real window — ortho_only (direct `run_prediction`)

- Crop: 4096×4096 from ATTANUR_4 at row0=19833, col0=6803 (raster center; no alignment vertices on this tile)
- Tiles: 100
- Selected model: `best_binary_unet_v5.pth`
- Device: cpu
- Model load: 1.2 s
- **Job duration: 800.2 s (~13.3 min)**
- Inference: ~100 tiles / ~800 s ≈ **8 s/tile** (TTA-4)
- Features: **1** (`partial`, blockage_pct 36, structural_damage true)
- Thumbnails: **1** (`images/0001.jpg`)
- GeoJSON: EPSG:4326 centroid ≈ (77.10483, 16.19479)
- Output: `backend/data/projects/phase15/predictions/p15_ortho/`

### 2. ATTANUR_4 window + TLBC shapefile — alignment (before skip fix)

- 462 features, all `clear`, **0 thumbnails** — entire network emitted for a window that contains **no** alignment vertices.
- Fixed (see comparison doc). Re-run of analysis on this window after the fix: **0 in-window reaches** (correct).

### 3. SHAKAPUR real window — ortho_plus_alignment

- Crop: 4096×4096 from SHAKAPUR at row0=17894, col0=41776 (median of 38 in-bounds vertices)
- Raster: 88528×41855, 4-band, EPSG:32643, 0.03425 m
- **Job duration: 808.1 s**
- Features: **2** (both `moderate`, damage false)
- Thumbnails: **2**
- Centroid sample: (77.11176, 16.16235)
- Output: `backend/data/projects/phase15/predictions/p15_shakapur_align/`

### 4. API smoke (user path without browser)

Backend: `uvicorn app.main:app --host 127.0.0.1 --port 8000`

```
POST /api/v1/projects  → 14aaa0c9-3a23-4174-bfcd-b69dee5729a8
POST /api/v1/projects/{id}/predictions  (attanur4_real_window.tif)
  job_id 363bd93a-1e22-48ee-9a19-49cb5096480a
  prediction_id 91dacd64-159c-4da3-830d-8a2308a6b8e8
  status queued → running (tile progress 12→44) → completed
GET /api/v1/jobs/{job_id}
GET /api/v1/predictions/{id}
GET /api/v1/predictions/{id}/geojson
GET /api/v1/predictions/{id}/images/0001.jpg  → 200, 64223 bytes, JPEG
```

API wall time: **2026-08-24 13:00:47Z → 13:20:23Z (~19.6 min)** including upload and model load in the worker.

Frontend `npm run dev` has been used on `:5173` in this repo; **map click / visual inspect was not automated in this session**.

## Commands executed

```
backend/.venv/Scripts/python.exe  (inspect rasters, CUDA)
PYTHONPATH=backend  python scripts/phase15_validate.py
PYTHONPATH=backend  python  (SHAKAPUR crop + run_prediction alignment)
PYTHONPATH=backend  python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
python -m unittest tests.test_phase1.TestAlignmentSkipsOutOfBounds tests.test_phase1.TestTileGrid tests.test_phase1.TestArchitecture
pip install pyshp
```

## Fixes applied (minimum)

1. Install **pyshp** in the product venv (shapefile alignment crashed with `INVALID_ALIGNMENT`).
2. Tile **progress** during mosaic inference (jobs no longer sit at 12% for the whole UNet pass).
3. Skip alignment reaches with **no `bbox_px`** (out-of-raster segments).
4. Safe `np.divide` for the probability mosaic (NaN warning on real windows).

## Remaining blockers / limitations

- Full ATTANUR_4 / ATTANUR_2 mosaics not timed on this CPU.
- `best_binary_unet_v5_lines.pth` still missing.
- No 07 blockage GeoTIFF/npz to compare masks.
- Production `boxes.geojson` is not UNet output — do not treat count 191 vs window count 1 as a model error.
- Peak RSS not recorded.
- Browser map interaction unverified.

## Phase 2

Not started.
