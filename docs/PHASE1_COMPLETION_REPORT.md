# Phase 1 completion report

Phase 1 delivers one standalone flow: frontend + FastAPI + local async jobs + the reference UNet canal pipeline (ortho-only and ortho+alignment) + canonical EPSG:4326 GeoJSON + reach thumbnails.

This is **not** a claim that the full reference notebooks were reproduced on production orthomosaics, and it is **not** model-accuracy validation.

## Implemented modules

| Area | Modules |
|------|---------|
| Entry | `backend/app/pipeline/run.py` (`run_prediction`) |
| IO | `pipeline/io/raster_reader.py` (RGB and RGBA) |
| Model | `pipeline/models/canal_model.py`, `registry.py` |
| Detection | `detection/canal_detection.py`, `blockage_detection.py`, `alignment_analysis.py` |
| Processing | `processing/postprocessing.py`, `blockage_scoring.py`, `reach_analysis.py` |
| Geospatial | `geospatial/alignment.py`, `geospatial/corridor.py` |
| Export | `export/geojson.py`, `export/thumbnails.py` |
| Jobs / API | `services/job_service.py`, `pipeline_service.py`, `result_service.py`, `api/routes/projects.py`, `predictions.py`, `jobs.py` |
| Errors | `core/errors.py` |
| Frontend | project create + ortho upload + optional alignment + job poll + Leaflet map + reach inspect |

## Reference source mapping

See `PHASE1_IMPLEMENTATION_MAPPING.md`. Summary:

- 05 UNet-ResNet50 → `canal_model.py`
- 07 tiled inference / TTA / FIC width filter / corridor / ortho blockage & damage → existing `canal_detection`, `postprocessing`, `corridor`, `blockage_*`
- `predict_segments.py` / `line_blockage.py` / `detect_damage.py` → `alignment_analysis.py`
- `box_images` / production GeoJSON idea → `thumbnails.py` + `geojson.py`

Intentionally unused at runtime: notebooks 03/04/06/08, FIC UNet, silt, DSM/DTM, Water-bodies.

## Files changed (high level)

- Backend pipeline, config, errors, DB (`Project`, job alignment/prediction columns), prediction/project routes
- Frontend: `App.tsx`, `AlignmentUpload.tsx`, `ReachMap.tsx`, `ResultsDashboard.tsx`, `analyzeImage.ts` / `pipeline.ts`
- Tests: `backend/tests/test_phase1.py`, `test_api.py`
- Docs: this file, `PHASE1_IMPLEMENTATION_MAPPING.md`, `.env.example`

A duplicate `api_router` in `backend/app/api/routes/__init__.py` that dropped `/projects` and `/predictions` was fixed.

## API endpoints (Phase 1)

| Method | Path | Notes |
|--------|------|--------|
| POST | `/api/v1/projects` | Create project |
| GET | `/api/v1/projects` | List |
| POST | `/api/v1/projects/{project_id}/predictions` | `ortho_file` required GeoTIFF; `alignment_files` optional `.geojson` or `.shp`+`.shx`+`.dbf` |
| GET | `/api/v1/jobs/{job_id}` | `queued` / `running` / `completed` / `failed` + `progress` + `message` |
| GET | `/api/v1/predictions/{prediction_id}` | Completed payload |
| GET | `/api/v1/predictions/{prediction_id}/geojson` | Canonical FeatureCollection |
| GET | `/api/v1/predictions/{prediction_id}/images/{image_name}` | Thumbnail bytes |

Jobs run on a **daemon thread** when `USE_CELERY=false` (Phase 1 default). Celery remains available if already configured.

Legacy `POST /api/v1/jobs` and DSM/DTM upload routes still exist but are not the Phase 1 UI path.

## Frontend changes

- GeoTIFF-first upload; optional alignment (GeoJSON or shapefile sidecars)
- Polls job until complete; does not mock once the API is used (`VITE_USE_MOCK` still available)
- Map of reach polygons; click shows thumbnail, blockage status/percent, structural damage, `model_version`, `pipeline_mode`
- Banner: **model prediction** vs **rule/alignment-assisted** — not field verified

Typecheck: `npx tsc -b` succeeded. Leaflet + `@types/leaflet` added. End-to-end UI was not exercised in a browser in this session (dev server was not running during verification).

## Tests run

Command (backend venv):

```
python -m unittest tests.test_phase1 tests.test_api tests.test_blockage
```

## Test results

**20 tests OK** (plus blockage tests included in that run). Coverage:

1. UNet-ResNet50 architecture construction (no checkpoint)
2. Weight selection: `_lines.pth` then `_v5.pth`; missing → `MODEL_NOT_AVAILABLE`
3. Canonical GeoJSON schema / `blocked` → `full`
4. CRS warp to EPSG:4326
5. Alignment GeoJSON load + reproject
6. Missing shapefile sidecars
7. Canonical status mapping / alignment % bins
8. Thumbnail relative `images/0001.jpg`
9. Job create → `queued`
10. Synthetic 512 GeoTIFF smoke (fake predictor) — **not accuracy**
11. Synthetic RGB ortho + alignment GeoJSON smoke (fake predictor)
12. Health + POST `/projects` + missing job 404

`sqlalchemy` was listed in `requirements.txt` but missing from the venv; it was installed so job/API tests can run.

## Known limitations

- Ortho-only reach extraction still depends on 07 morphology/skeleton logic; a tiny synthetic raster may produce **zero features**. That does not mean the production path is empty.
- Alignment damage/blockage uses RGB rules from the reference scripts, not a second neural net.
- Corridor width is config (`CORRIDOR_WIDTH_M` / `CORRIDOR_BUFFER_M`, default 35 m), not a frontend control.
- Shapefile CRS without `.prj` is rejected unless coordinates look like lon/lat.
- `POST /uploads` still allows DSM/DTM; Phase 1 UI does not send them; silt is not run.
- Default `encoder_weights=None` at architecture build; ImageNet is not downloaded for checkpoint load.

## Missing reference assets still required

- **`best_binary_unet_v5_lines.pth`** — not present. Runtime falls back to **`best_binary_unet_v5.pth`** (present under `backend/app/models/model_weights/`). `model_version` will be that filename.
- Production **orthomosaics**, DSM/DTM, and reference GeoJSON from Canal Pipeline — not in this repo. Full mosaic jobs were not run here.
- Do not treat notebook 07 last-executed outputs as a substitute for those files.

## Intentionally deferred to Phase 2+

Google auth, accounts, permissions, retraining UI, correct/incorrect training loop, polygon/pixel annotation, silt, DSM/DTM processing, FIC UNet, Water-bodies, model architecture changes, cloud/K8s packaging.

## How to run locally

Backend (from `backend/`, venv): `USE_CELERY=false`, `STORAGE_BACKEND=local`, then uvicorn on port 8000.

Frontend: `npm run dev` (proxies `/api` to `:8000`). Upload a GeoTIFF; optionally alignment; wait for the job; inspect the map.

Keep secrets out of git. Prefer `backend/.env.example` for path names; do not commit live cloud credentials.
