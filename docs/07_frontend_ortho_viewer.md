# Frontend: Ortho + Chainage Inspection Viewer

Frontend viewer + backend export are wired for live predictions.

## Frontend (`frontend/`)

- `ChannelSection.tsx` — SVG plan-view of the canal channel
- `ChainageLightbox.tsx` — fullscreen inspection (live `images/NNNN.jpg` filmstrip)
- `ReachMap.tsx` — `L.imageOverlay` when `outputs.ortho_preview` + `metadata.ortho_bounds`
  are present; OSM fallback otherwise; Drone ortho / Base map toggle
- `ResultsDashboard.tsx` — map/table click opens lightbox
- `pipeline.ts` — `orthoPreviewUrl(id)` → `GET /api/v1/predictions/{id}/ortho`

## Backend (`backend/app`)

1. `pipeline/export/ortho_preview.py` — downsampled RGB JPEG (long edge ~2048) +
   WGS84 `ortho_bounds` `[[south, west], [north, east]]`
2. `GET /api/v1/predictions/{id}/ortho` — serves `ortho_preview.jpg`
3. `result.geojson` metadata includes `ortho_bounds`; `outputs.ortho_preview` in `result.json`
4. Alignment path emits one GeoJSON feature + thumbnail per ~50 m chainage
