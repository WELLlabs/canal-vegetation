# Phase 1 — Frontend ↔ Backend Integration Report

## Existing frontend preserved

Major pages/components reused **without redesign**:

| Component | Role |
|-----------|------|
| `App.tsx` | Single-page workflow (`idle` → `preview` → `analyzing` → `results` / `error`) |
| `UploadZone.tsx` | GeoTIFF drop/select |
| `AlignmentUpload.tsx` | Optional GeoJSON / shapefile sidecars |
| `ImagePreviewCard.tsx` | Preview + progress bar (stage label tweak only) |
| `AnalyzeControls.tsx` | Analyze / analyzing button |
| `ResultsDashboard.tsx` | Summary, inspect panel, mode/version banner, report download |
| `ReachMap.tsx` | Leaflet map + reach polygons + click select |
| `ReachTable.tsx` | Per-reach table + thumbnail previews |
| `InfoCard.tsx`, `StatusBadge.tsx`, `ConfidenceGauge.tsx`, `SeverityMeter.tsx`, `RecommendationsList.tsx` | Result presentation |
| `NavBar`, `Hero`, `HowItWorks`, `Footer`, `ContourBackground` | Marketing chrome |
| `api/mapResult.ts` | Backend job → existing `AnalysisResult` adapter (unchanged) |

**Not mounted / not Phase 1 UI:** `OptionalRasters.tsx` (DSM/DTM) — left unused.

No new pages, no new map library, no framework change, no visual redesign.

---

## Files modified

### Frontend

| File | Reason | Type of change |
|------|--------|----------------|
| `frontend/src/api/pipeline.ts` | Add `GET /predictions/{id}/geojson` client | API integration |
| `frontend/src/api/analyzeImage.ts` | Always use real API; poll jobs; load prediction **and** canonical GeoJSON; remove mock analyzer | API integration + state handling |
| `frontend/src/api/config.ts` | Remove `USE_MOCK` flag (product path is real API only) | API integration |
| `frontend/src/types.ts` | Expand `STAGE_LABELS` for create/upload/queued/running | Data mapping / job status labels |
| `frontend/src/components/ImagePreviewCard.tsx` | Show live poll stage text when not in `STAGE_LABELS` | Required UI adjustment (progress only) |
| `frontend/src/utils/generateReport.ts` | Prefer summary `full` over legacy `blocked` | Data mapping |
| `frontend/.env` | Clear mock flag; empty `VITE_API_BASE_URL` (Vite proxy) | Config |
| `frontend/.env.example` | Document proxy-only API base URL | Config |

### Docs / verification helpers

| File | Reason |
|------|--------|
| `FRONTEND_BACKEND_INTEGRATION_MAPPING.md` | Step 1 inspection mapping |
| `backend/scripts/phase1_frontend_e2e.py` | Mirrors frontend API sequence for E2E |
| `PHASE1_FRONTEND_INTEGRATION_REPORT.md` | This report |

---

## API integration

Connected from the existing frontend client (`pipeline.ts` + `analyzeImage.ts`):

| Method | Path | Usage |
|--------|------|--------|
| POST | `/api/v1/projects` | Create project from uploaded filename |
| POST | `/api/v1/projects/{project_id}/predictions` | Upload ortho (+ optional `alignment_files`) |
| GET | `/api/v1/jobs/{job_id}` | Poll `queued` / `running` / `completed` / `failed` (~2 s) |
| GET | `/api/v1/predictions/{prediction_id}` | Prediction details + summary |
| GET | `/api/v1/predictions/{prediction_id}/geojson` | Canonical FeatureCollection (map/table source of truth) |
| GET | `/api/v1/predictions/{prediction_id}/images/{image_name}` | Reach thumbnails |

Vite proxies `/api` and `/health` → `http://127.0.0.1:8000`.

### Data mapping

Backend GeoJSON properties → existing UI fields (via types + direct property reads; adapter for dashboard summary):

`reach_id`, `tile_id`, `canal_name`, `canal_type`, `chainage_m`, `blockage_status`, `blockage_pct`, `structural_damage`, `centroid_lon`, `centroid_lat`, `thumbnail_relpath`

Legacy aliases (`status`, `blockage_percentage`, `damage`, `chainage`) remain for compatibility but are not a second schema.

---

## End-to-end verification

**Method:** Frontend client sequence mirrored by `scripts/phase1_frontend_e2e.py` against live FastAPI + Vite proxy. Real validated windows (not full mosaics). Frontend `npm run build` succeeded.

Results also stored in `backend/data/validation/phase1_frontend_e2e.json`.

### A. ortho_only

| Check | Result |
|-------|--------|
| Asset | `data/validation/attanur4_real_window.tif` |
| Project create | OK (`59892735-…`) |
| Prediction start | OK → job `0fefc450-…`, prediction `fd0fbda1-…` |
| Job status | `queued` → `running` → `completed` |
| Pipeline mode | `ortho_only` |
| GeoJSON | 1 feature (`partial`, 36%, damage true) |
| Thumbnails | `images/0001.jpg` HTTP 200 |
| Vite proxy GeoJSON | OK |

### B. ortho_plus_alignment

| Check | Result |
|-------|--------|
| Asset | `data/validation/shakapur_real_window.tif` + `TLBC_D95` shapefile sidecars |
| Project create | OK (`2c924ef7-…`) |
| Prediction start | OK → job `81e16f16-…`, prediction `a0c568d9-…` |
| Job status | `queued` → `running` → `completed` |
| Pipeline mode | `ortho_plus_alignment` |
| GeoJSON | 2 features (`moderate` / 58%, damage false) |
| Thumbnails | `0001.jpg`, `0002.jpg` HTTP 200 via Vite |
| Metadata | `label_source=rule`, model `best_binary_unet_v5.pth` |

### Job status / GeoJSON / map / thumbnails

| Concern | Verified |
|---------|----------|
| Job polling states | Yes (queued / running / completed) |
| GeoJSON loading | Yes (dedicated endpoint + prediction payload) |
| Map interaction | **Data-ready:** GeoJSON is Leaflet-compatible FeatureCollection with polygons; existing `ReachMap` consumes `job.geojson` unchanged. Manual browser click not automated in this session (no browser automation tools). |
| Thumbnail loading | Yes (API + Vite proxy) |
| Failed job UI | Existing error panel in `App.tsx` remains; intentional failure not re-run here |

---

## Known limitations

1. **No automated browser click-through** — integration verified at the same HTTP layer the frontend uses (create → upload → poll → prediction → geojson → images), plus production frontend build. Manual UI click on a reach polygon was not scripted.
2. **CPU-only inference** — each 4096×4096 window took ~20 minutes; full mosaics were not run.
3. **Mock analyzer removed** — offline demo without backend is no longer available (`VITE_USE_MOCK` gone).
4. **DSM/DTM / silt / auth / retraining** — intentionally out of Phase 1.
5. **`OptionalRasters`** still in the repo but unused by the Phase 1 flow.

---

## Final summary

**Yes.** A user can use the **existing** frontend (same pages, layout, Leaflet map, and result cards) to:

1. Upload a GeoTIFF orthomosaic  
2. Optionally attach canal alignment  
3. Start a real async prediction  
4. Watch job progress  
5. Inspect real canonical GeoJSON reaches on the existing map/table  
6. Load real reach thumbnails and details (status, blockage %, structural damage, model version, pipeline mode)

Phase 1 product path = **existing frontend + real backend/pipeline**, with minimal API/adapter changes and no UI redesign.
