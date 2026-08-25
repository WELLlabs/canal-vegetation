# Canal Blockage Detection — Phase 1

Local web application for canal blockage analysis from drone orthomosaics.

Upload a GeoTIFF, optionally attach a canal alignment, run an async AI pipeline, then inspect reaches on an interactive map with GeoJSON + thumbnails.

## What the application does

* **GeoTIFF upload** — RGB/RGBA orthomosaic (`.tif` / `.tiff`)
* **Optional canal alignment** — GeoJSON or shapefile (with sidecars)
* **AI-based canal analysis** — tiled UNet inference (`best_binary_unet_v5.pth`)
* **Blockage detection** — per-reach status: `clear` / `partial` / `moderate` / `full` + `blockage_pct`
* **Structural damage detection** — boolean flag per reach
* **GeoJSON output** — canonical EPSG:4326 FeatureCollection
* **Reach thumbnails** — JPEG previews per reach
* **Interactive map inspection** — existing Leaflet UI: click a polygon → details + thumbnail

This is **not** field-verified labeling. Results are model or alignment-assisted predictions.

## Supported modes

### Ortho Only

```
GeoTIFF → AI prediction → canal / reach analysis → GeoJSON + thumbnails
```

### Ortho + Alignment

```
GeoTIFF + Shapefile/GeoJSON → alignment-assisted reach analysis → GeoJSON + thumbnails
```

## Architecture

```
┌────────────────────┐     POST /projects + /predictions      ┌─────────────────────┐
│  Frontend (Vite)   │ ─────────────────────────────────────► │  FastAPI (uvicorn)  │
│  React + Leaflet   │ ◄──── GET /jobs, /predictions, … ──── │  /api/v1/*          │
└────────────────────┘         (dev proxy /api → :8000)       └──────────┬──────────┘
                                                                         │
                                                              async local job thread
                                                              (USE_CELERY=false)
                                                                         │
                                                                         ▼
                                                              ┌─────────────────────┐
                                                              │  Pipeline           │
                                                              │  UNet + postprocess │
                                                              │  GeoJSON + thumbs   │
                                                              └─────────────────────┘
                                                                         │
                                                                         ▼
                                                              data/projects/.../predictions/
```

## Quick Start

**Requirements:** Python **3.11+** (validated on 3.13), Node.js 18+, model weights file (see below).

### 1. Backend

```bash
cd backend
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS / Linux
# source .venv/bin/activate

pip install -r requirements.txt
copy .env.example .env          # Windows
# cp .env.example .env          # macOS / Linux

# Place weights at:
#   backend/app/models/model_weights/best_binary_unet_v5.pth

python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Prefer `python -m uvicorn` over calling `uvicorn.exe` directly (avoids broken shim issues on some Windows setups).

Health check: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

### 2. Frontend

```bash
cd frontend
npm install
copy .env.example .env          # optional; empty VITE_API_BASE_URL uses the Vite proxy
npm run dev
```

UI: [http://127.0.0.1:5173](http://127.0.0.1:5173)

### Minimum startup (already set up)

```bash
# terminal 1 — from backend/
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# terminal 2 — from frontend/
npm run dev
```

### Required layout

| Item | Path |
|------|------|
| Python env | `backend/.venv` |
| Env file | `backend/.env` (from `.env.example`) |
| Model weights | `backend/app/models/model_weights/best_binary_unet_v5.pth` |
| Uploads | `backend/data/uploads/` |
| Predictions / GeoJSON / thumbs | `backend/data/projects/{project_id}/predictions/{prediction_id}/` |
| Job DB | `backend/data/jobs.db` |
| Validation windows (optional) | `backend/data/validation/*.tif` |

## Input Requirements

### GeoTIFF

* Extensions: `.tif` / `.tiff`
* Georeferenced orthomosaic (CRS present)
* RGB or RGBA (alpha used for valid-pixel masking)
* Large full mosaics work but are **slow on CPU** (thousands of tiles)

### Alignment (optional)

**GeoJSON / JSON**

* Upload one `.geojson` or `.json` file with canal centerline geometry

**Shapefile**

* Upload together: `.shp` + `.shx` + `.dbf` (required)
* `.prj` recommended; `.cpg` optional
* Use the multi-file alignment picker in the UI

## Output

Stored under `data/projects/{project_id}/predictions/{prediction_id}/`:

* `result.geojson` — canonical FeatureCollection (EPSG:4326)
* `result.json` — summary + metadata
* `images/*.jpg` — reach thumbnails

### Canonical feature properties

| Property | Meaning |
|----------|---------|
| `reach_id` | Reach identifier |
| `tile_id` | Source raster id |
| `canal_name` / `canal_type` | Canal metadata (alignment mode) |
| `chainage_m` | Chainage along alignment (m) |
| `blockage_status` | `clear` \| `partial` \| `moderate` \| `full` |
| `blockage_pct` | Blockage percentage |
| `structural_damage` | Boolean |
| `centroid_lon` / `centroid_lat` | WGS84 centroid |
| `thumbnail_relpath` | e.g. `images/0001.jpg` |

GeoJSON `metadata` includes `pipeline_mode`, `model_version`, `label_source`.

## API

Base prefix: `/api/v1`

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/projects` | Create project |
| GET | `/projects` | List projects |
| POST | `/projects/{project_id}/predictions` | Upload ortho (+ optional alignment), start job |
| GET | `/jobs/{job_id}` | Job status / progress |
| GET | `/predictions/{prediction_id}` | Prediction payload |
| GET | `/predictions/{prediction_id}/geojson` | Canonical GeoJSON |
| GET | `/predictions/{prediction_id}/images/{image_name}` | Thumbnail bytes |
| GET | `/health` | Health check |

Job statuses used by the UI: `queued` → `running` → `completed` / `failed`.

## Validation

Validation used **georeferenced windows** cropped from real orthomosaics — **not** complete 5000+ tile mosaics.

| Mode | Window | Result (representative) |
|------|--------|-------------------------|
| `ortho_only` | ATTANUR_4 4096×4096 | 1 reach, `partial` @ 36%, structural damage true, 1 thumbnail |
| `ortho_plus_alignment` | SHAKAPUR 4096×4096 + TLBC shapefile | 2 reaches, both `moderate` @ 58%, 2 thumbnails |

See `PHASE1_5_REAL_DATA_VALIDATION.md`, `PHASE1_FRONTEND_INTEGRATION_REPORT.md`, and `backend/data/validation/phase1_frontend_e2e.json`.

## Known Limitations

* Full orthomosaics are slow on CPU (~hours for 5000+ tiles)
* Preferred checkpoint `best_binary_unet_v5_lines.pth` is **unavailable**; runtime uses `best_binary_unet_v5.pth`
* Real-data validation was on **windows**, not full mosaics
* No authentication
* No retraining / training UI
* No DSM/DTM or silt analysis in Phase 1
* Results are predictions, not field surveys

## Tests

From `backend/` (no full orthomosaic run):

```bash
python -m unittest discover -s tests -v
```

## Project docs

| Doc | Contents |
|-----|----------|
| `PHASE1_FINAL_HANDOVER.md` | Demo handover |
| `PHASE1_FRONTEND_INTEGRATION_REPORT.md` | Frontend ↔ API wiring |
| `PHASE1_5_REAL_DATA_VALIDATION.md` | Real-window validation |
| `PHASE1_COMPLETION_REPORT.md` | Phase 1 implementation summary |
| `FRONTEND_BACKEND_INTEGRATION_MAPPING.md` | Component ↔ endpoint map |

## License / notes

Internal Phase 1 demo build. Do not treat outputs as certified field verification.
