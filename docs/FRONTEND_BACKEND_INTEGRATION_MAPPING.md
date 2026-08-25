# Frontend ↔ Backend Integration Mapping

Inspection-only document for Phase 1 finalization.  
**Rule:** preserve existing UI; connect real API data only.

## Current frontend surface

| Area | Location | Notes |
|------|----------|-------|
| Routes / pages | Single-page `App.tsx` (no router) | Stages: `idle` → `preview` → `analyzing` → `results` / `error` |
| Upload UI | `UploadZone.tsx` | GeoTIFF `.tif` / `.tiff` only |
| Alignment UI | `AlignmentUpload.tsx` | Optional GeoJSON or shapefile + sidecars |
| Preview / progress | `ImagePreviewCard.tsx` + `AnalyzeControls.tsx` | Progress bar + stage label |
| Results | `ResultsDashboard.tsx` | Summary cards, inspect panel, report download |
| Map | `ReachMap.tsx` (Leaflet) | Reach polygons, click → select |
| Reach table | `ReachTable.tsx` | Per-reach rows + thumbnails |
| Cards | `InfoCard.tsx`, `StatusBadge.tsx`, `ConfidenceGauge.tsx`, `SeverityMeter.tsx`, `RecommendationsList.tsx` | Presentational |
| Marketing chrome | `NavBar`, `Hero`, `HowItWorks`, `Footer`, `ContourBackground` | Unchanged |
| Unused (Phase 1) | `OptionalRasters.tsx` | DSM/DTM UI exists but is **not** mounted in `App.tsx` |
| API client | `api/pipeline.ts`, `api/analyzeImage.ts`, `api/config.ts` | Real endpoints when `VITE_USE_MOCK=false` |
| Adapter | `api/mapResult.ts` | Backend job → existing `AnalysisResult` shape |
| Types | `types.ts` | Canonical + legacy alias fields |

**Mock / demo:** `analyzeImage.ts` still contains `mockAnalyze`, gated by `VITE_USE_MOCK`. `.env` sets `VITE_USE_MOCK=false`. No static GeoJSON is hard-coded in map components.

---

## Component → data source → endpoint → required change

### Existing Upload Component (`UploadZone`)
→ Local file selection only (no network)
→ *(none — feeds App state)*
→ **No change** (preserve)

### Existing Alignment Upload (`AlignmentUpload`)
→ Local multi-file selection
→ Passed into `POST /projects/{project_id}/predictions` as `alignment_files`
→ **No change** (already wired via App → `analyzeImage`)

### Existing Analyze Controls (`AnalyzeControls`)
→ Calls App `handleAnalyze`
→ Triggers create project + prediction start
→ **No change**

### Existing Image Preview / Progress (`ImagePreviewCard`)
→ App state: `progress`, `currentStage`
→ `GET /jobs/{job_id}` (via poll in `analyzeImage`)
→ **Minimal:** show raw stage string when not in `STAGE_LABELS` (queued / running / backend stages)

### Existing App workflow (`App.tsx`)
→ `analyzeImage(file, onProgress, { alignmentFiles })`
→ Orchestrates all Phase 1 endpoints
→ **Prefer no UI redesign**; keep stage machine as-is

### Existing API orchestrator (`api/analyzeImage.ts`)
→ Real API when mock off; still has mock fallback
→ `POST /projects` → `POST .../predictions` → poll `GET /jobs/{id}` → `GET /predictions/{id}`
→ **Replace/remove mock path for connected mode**; **also fetch** `GET /predictions/{id}/geojson` and merge into payload

### Existing Pipeline client (`api/pipeline.ts`)
→ fetch wrappers for projects / predictions / jobs / images
→ Missing dedicated GeoJSON helper
→ **Add** `getPredictionGeojson(predictionId)` → `GET /api/v1/predictions/{id}/geojson`

### Existing Adapter (`api/mapResult.ts`)
→ Maps `JobResult.summary` → `AnalysisResult` (confidence, severity, recommendations)
→ Consumes backend summary + features
→ **Keep as single adapter**; do not invent a second frontend schema

### Existing Types (`types.ts`)
→ `ReachProperties` already includes canonical backend fields + legacy aliases
→ Backend GeoJSON properties
→ **No competing schema**; adapter/components already prefer canonical names

### Existing Results Dashboard (`ResultsDashboard`)
→ `result.job` (prediction payload)
→ Displays mode, model version, selected reach details, thumbnails via image URL helper
→ **No redesign**; ensure job payload includes real GeoJSON + metadata

### Existing Results Map (`ReachMap`)
→ `job.geojson` FeatureCollection (Leaflet `L.geoJSON`)
→ `GET /predictions/{id}/geojson` (canonical source of truth)
→ **Replace data source only** if prediction body GeoJSON is empty; do not replace Leaflet

### Existing Reach Table (`ReachTable`)
→ `job.features` or `job.geojson.features`
→ Same prediction / GeoJSON data
→ **No change** (already uses canonical `blockage_status`, `blockage_pct`, `structural_damage`, `thumbnail_relpath`)

### Existing Thumbnail / Image Display (dashboard + table)
→ `predictionImageUrl(predictionId, thumbnail_relpath)`
→ `GET /predictions/{prediction_id}/images/{image_name}`
→ **No change** (URL helper already correct)

### Existing Report Download (`utils/generateReport.ts`)
→ Local text blob from `AnalysisResult`
→ Uses summary fields from job
→ **Optional minor:** prefer `full` over legacy `blocked` in text report

### Existing Marketing / chrome components
→ Static copy
→ *(none)*
→ **No change**

---

## Backend endpoints to connect (Phase 1)

| # | Method | Path | Frontend consumer |
|---|--------|------|-------------------|
| 1 | POST | `/api/v1/projects` | `createProject` |
| 2 | POST | `/api/v1/projects/{project_id}/predictions` | `startPrediction` |
| 3 | GET | `/api/v1/jobs/{job_id}` | `getJobStatus` (poll) |
| 4 | GET | `/api/v1/predictions/{prediction_id}` | `getPrediction` |
| 5 | GET | `/api/v1/predictions/{prediction_id}/geojson` | **to add** `getPredictionGeojson` |
| 6 | GET | `/api/v1/predictions/{prediction_id}/images/{image_name}` | `predictionImageUrl` |

Job statuses required in UI: `queued` → `running` → `completed` / `failed`.

---

## Canonical GeoJSON property mapping

Backend (source of truth) → Existing frontend field:

| Backend property | Frontend usage |
|------------------|----------------|
| `reach_id` | Map / table / inspect header |
| `tile_id` | Typed; optional display |
| `canal_name` | Typed |
| `canal_type` | Typed |
| `chainage_m` | Table (alias: `chainage`) |
| `blockage_status` | Map color, table, InfoCard (alias: `status`) |
| `blockage_pct` | Table, InfoCard (alias: `blockage_percentage`) |
| `structural_damage` | Table, InfoCard (alias: `damage`) |
| `centroid_lon` / `centroid_lat` | In GeoJSON / types |
| `thumbnail_relpath` | Image URL builder |

Adapter layer: `mapResult.jobResultToAnalysis` for dashboard summary cards; reach-level fields read directly from GeoJSON properties.

---

## Preferred change order (minimize UI edits)

1. `api/pipeline.ts` — add GeoJSON GET
2. `api/analyzeImage.ts` — wire GeoJSON fetch; remove mock for connected product path
3. `api/mapResult.ts` — only if payload shape gaps appear
4. `types.ts` / `STAGE_LABELS` — job status labels if needed
5. `ImagePreviewCard.tsx` — **only if** stage display must show poll messages (required for job UX)

**Do not** redesign pages, replace Leaflet, duplicate upload/results UI, or mount DSM/DTM (`OptionalRasters`) for Phase 1.
