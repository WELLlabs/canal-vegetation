# Phase 1.5 — Reference comparison

Source of truth: `D:\Github\Canal Pipeline` notebooks/scripts listed below. Product: `d:\Github\canal-vegetation`.

## A. Model

| Check | Reference | Product | Class | Match |
|-------|-----------|---------|-------|--------|
| Architecture | 07 Cell 2: `smp.Unet(encoder_name='resnet50', encoder_weights=None, in_channels=3, classes=1)` | `canal_model.build_canal_unet` | — | **EXACT MATCH** |
| 3-channel | 07 Cell 3: `data[:3]` after RGBA read | `read_window_rgba` uses bands 1–3; RGB-only rasters allowed | LOW | **EXPECTED PRODUCT DIFFERENCE** (notebook hard-fails without band 4) |
| Normalization | ImageNet mean/std on `/255` CHW | Same tensors in `CanalModel.predict_tile` | LOW | **EXACT MATCH** (norm on device vs CPU then `.to(DEVICE)` — numerically equivalent) |
| Checkpoint | 07 Cell 1 `MODEL_NAME = best_binary_unet_v5_lines.pth`; Cell 2 `encoder_weights=None` then `load_state_dict` | Prefer `_lines.pth` then `_v5.pth`; never random | CRITICAL if wrong file | **EXPECTED PRODUCT DIFFERENCE**: `_lines.pth` **missing**; loaded **`best_binary_unet_v5.pth`**. Filename recorded as `model_version`. |
| TTA autocast | 07 Cell 2: always `torch.amp.autocast('cuda')` | CUDA autocast only; CPU `nullcontext` | LOW | **EXPECTED PRODUCT DIFFERENCE** (notebook would be wrong/broken on CPU) |

Unit test: UNet-ResNet50 parameter count 32521105.

## B. Inference

| Check | Reference | Product | Class | Match |
|-------|-----------|---------|-------|--------|
| TILE / STEP / DS / thr | 07 Cell 2–3: 512 / 384 / 8 / 0.4 | config defaults | — | **EXACT MATCH** |
| Tile grid | `range(0, dim - tile + 1, step)` | `iter_tile_offsets` | HIGH if wrong | **EXACT MATCH** (unit test) |
| Valid mask | `alpha == 255`, skip if `< 0.3` of tile | same `min_valid_frac=0.3` | — | **EXACT MATCH** for RGBA |
| Overlap average + DS mean | Cell 3 reshape mean | `predict_probability_mosaic` | — | **EXACT MATCH** |
| TTA | 4 rotations, mean sigmoid | `tta_predict_4` | — | **EXACT MATCH** |
| Pixel size | 07 config table 0.0352 for ATTANUR_4 | `abs(transform.a)` = 0.0351849 | LOW | **EXPECTED PRODUCT DIFFERENCE** (geotransform is more accurate) |

## C. Postprocessing

| Check | Reference | Product | Class | Match |
|-------|-----------|---------|-------|--------|
| Morphology | Cell 6 `classify_canal_components`: OPEN 1, CLOSE **2**, ellipse 5 | `postprocessing.py` | CRITICAL vs Cell 3 CLOSE 1 | **EXACT MATCH** of **Cell 6** (the function actually applied after Cell 5 params). Cell 3 leftover CLOSE=1 is a **REFERENCE INCONSISTENCY**. |
| CC 8-connected | Cell 6 | same | — | **EXACT MATCH** |
| FIC/canal widths | Cell 5: area 50, aspect 2, skel 0.008, mean 1.6, max-min 2.2, max 28 | config | — | **EXACT MATCH** of Cell 5 (not Cell 2’s area 100 / skel 0.015 / max 15) |
| Corridor in 07 | Cell 7 always buffers `TLBC_D95.shp` at **35 m** | ortho_only: no corridor unless alignment uploaded | HIGH geometry | **EXPECTED PRODUCT DIFFERENCE** (locked product modes) |

## D. Alignment

| Check | Reference | Product | Class | Match |
|-------|-----------|---------|-------|--------|
| Load / CRS | 07 Cell 7 warps shapefile as EPSG:4326; `.prj` is GCS_WGS_1984 | `load_alignment` uses `.prj` then warp to raster CRS | LOW | **EXACT MATCH** for this shapefile |
| Corridor width | 35 m | `CORRIDOR_WIDTH_M` default 35 | — | **EXACT MATCH** |
| Scoring corridor | `predict_segments.py`: `hw = (0.5 + width/2)/px` | `analyze_alignment_reaches` same formula | — | **EXACT MATCH** |
| `detect_damage.py` width | type 14 m / 5 m, not 0.5+width/2 | product uses shapefile/type default widths (14/5/3.3) | MEDIUM | **EXPECTED PRODUCT DIFFERENCE** vs `detect_damage.py` if attribute `width` missing |
| Out-of-raster segments | `predict_segments` leaves veg None but still writes all network rows | **was** emitting 462 `clear` reaches + 0 thumbs on ATTANUR_4 window | **HIGH** | **FIXED**: skip if `bbox_px` is None. SHAKAPUR window after fix: 2 reaches, 2 thumbs. |
| pyshp | reference venv | product venv missing `shapefile` | **CRITICAL** (alignment unusable) | **FIXED**: `pip install pyshp` |

## E. Blockage / damage

### Ortho-only vs 07 Cells 9–10, 17

| Check | Reference | Product | Class | Match |
|-------|-----------|---------|-------|--------|
| Veg / silt-like / water features | Cell 9 | `compute_reach_features_and_blockage` | — | **EXACT MATCH** (same thresholds) |
| Score bins | Cell 10 veg 0.5/0.25/0.1; blocked if score≥3 or centerline≥0.45 | `blockage_scoring.score_reach`; internal status `blocked` | — | **EXACT MATCH** internally |
| Canonical `blocked`→`full` | product schema | export mapper | — | **EXPECTED PRODUCT DIFFERENCE** (API schema) |
| Structural | Cell 17 edges/texture; skip if already blocked | `detect_sd` + `_score_structural` | — | **EXACT MATCH** of that cell |

No 07 GeoTIFF/npz on disk → mask **not** compared. Window result (1 partial + damage) is **not** an accuracy claim.

### Alignment vs `predict_segments.py` / `detect_damage.py` / `line_blockage.py`

| Check | Reference | Product | Class | Match |
|-------|-----------|---------|-------|--------|
| Veg % classes | predict_segments: ≤5 / ≤30 / ≤80 | `classify_blockage_pct` | — | **EXACT MATCH** predict_segments |
| detect_damage bins | ≤5 / ≤40 / ≤70 | not used | MEDIUM | **EXPECTED PRODUCT DIFFERENCE** (Phase 1 mapping chose predict_segments for blockage) |
| Rocky damage | detect_damage measure + p95 threshold | `measure_veg_rock` + same p95 floor 0.04 | — | **EXACT MATCH** of that script’s measure/threshold |
| line_blockage | HALF_W 2.5 m, 3-class veg/water, 50 m reaches | 50 m reaches; 4-class veg%; width-based corridor | HIGH vs line_blockage 3-class | **EXPECTED PRODUCT DIFFERENCE** (mapping: predict_segments + detect_damage) |

## Output comparison

| Item | Reference artefact | Product | Classification |
|------|--------------------|---------|----------------|
| Predicted mask | 07 outputs missing | `canal_mask.tif` written under prediction dir | **UNEXPLAINED DIFFERENCE** not possible to score — artefact absent |
| Reach count | production attanur boxes **191** GIS features | ATTANUR_4 4096 window ortho_only: **1**; SHAKAPUR window alignment: **2** | **EXPECTED PRODUCT DIFFERENCE** (different area, UNet vs GIS boxes, window vs full mosaic) |
| Status / % / damage | production uses `blockpct` / string damage | canonical `blockage_status` / `blockage_pct` / bool | **EXPECTED PRODUCT DIFFERENCE** |
| CRS | processing UTM; production lon/lat | GeoJSON EPSG:4326 | **EXACT MATCH** of product requirement |
| Thumbnails | `images/NNNN.jpg` in production | same relative path; JPEG served by API | **EXACT MATCH** of packaging idea |

## Fixes applied (with source)

1. **pyshp** — `_load_shapefile` (`alignment.py`); observed `ModuleNotFoundError` on `TLBC_D95.shp`.
2. **Skip `bbox_px is None`** — `analyze_alignment_reaches` vs `predict_segments.py` skip-when-outside-bounds. Observed 462 empty clears on a non-overlapping window.
3. **Tile progress** — 07 Cell 3 prints `done/total`; product jobs froze at 12%.
4. **`np.divide(..., where=count_map>0)`** — Cell 3 `pred_sum/count_map`; real windows raised invalid-divide.

## Tests

- `TestTileGrid.test_matches_notebook_range`
- `TestAlignmentSkipsOutOfBounds` (SHAKAPUR real window + `TLBC_D95.shp`)
- Architecture / weight fallback (existing)

## Ready for Phase 2?

See `PHASE1_5_REAL_DATA_VALIDATION.md`: **READY WITH KNOWN LIMITATIONS**. Do not treat this as validated model accuracy.
