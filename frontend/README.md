# Canal Watch — AI Canal Blockage Detection (Frontend)

React + TypeScript + Vite frontend for canal blockage detection.
Phase 1 connects this **existing UI** to the real FastAPI + pipeline backend.

## Stack
- React 19 + TypeScript + Vite
- Tailwind CSS v4 (`@tailwindcss/vite`)
- Leaflet map (`ReachMap`)
- lucide-react for icons

## Getting started

```bash
# terminal 1 — API (from backend/)
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# terminal 2 — UI (from frontend/)
npm install
npm run dev
```

`vite.config.ts` proxies `/api` and `/health` to `http://127.0.0.1:8000`.
Copy `.env.example` to `.env` (leave `VITE_API_BASE_URL` empty for the proxy).

## Phase 1 API flow

Orchestrated by `src/api/analyzeImage.ts` + `src/api/pipeline.ts`:

1. `POST /api/v1/projects` — create project
2. `POST /api/v1/projects/{project_id}/predictions` — upload GeoTIFF (+ optional alignment)
3. `GET /api/v1/jobs/{job_id}` — poll `queued` / `running` / `completed` / `failed`
4. `GET /api/v1/predictions/{prediction_id}` — prediction details
5. `GET /api/v1/predictions/{prediction_id}/geojson` — canonical reach GeoJSON
6. `GET /api/v1/predictions/{prediction_id}/images/{image_name}` — reach thumbnails

## Project structure

```
src/
  api/analyzeImage.ts        # create → upload → poll → load results
  api/pipeline.ts            # HTTP helpers
  api/mapResult.ts           # backend job → AnalysisResult adapter
  api/config.ts              # API base URL / proxy helpers
  components/UploadZone.tsx
  components/AlignmentUpload.tsx
  components/results/ReachMap.tsx
  components/results/ResultsDashboard.tsx
  App.tsx
```
