# Canal Blockage App

Standalone web app for canal blockage (and optional silt) analysis from drone
orthophotos. Built on the WELL Labs canal-vegetation-model reference pipeline.

- One **fixed** approved blockage scorer (no model selection) plus an optional fixed canal-line refiner.
- **Bundled** canal alignments (TLBC D95 - Attanur, NRBC) plus **state centrelines**. Karnataka first: drop the shapefile in `backend/app/assets/regions/karnataka/`. Users usually upload imagery only and can provide an alignment override.
- Blockage scoring uses the fixed open-channel segmentation model. An optional canal-line U-Net refines the alignment before scoring; both run on CPU. Silt is estimated from a DSM and DTM pair.

## Layout
```
backend/   FastAPI + inference (Python)
  app/config/models/   <-- fixed blockage model + optional canal-line model
  app/assets/alignments/  bundled TLBC + NRBC reaches
  app/assets/regions/     state centrelines (karnataka first, then others)
  app/assets/national/    all-India fallback canal layer
frontend/  React + Vite + Tailwind + MapLibre
```

## Run with Docker (recommended)

Everything (Python, PyTorch CPU, GDAL/rasterio, the built frontend) is baked into
two images. Models are mounted from `backend/app/config/models/`, so they
are never copied into the image.

```
# from the canal-blockage-app/ folder
docker compose up --build
```

Then open http://localhost:8080

- Frontend (nginx) serves the UI and proxies `/api` to the backend, so there are no CORS issues and no size cap on orthophoto uploads.
- Backend API is also exposed on http://localhost:8000 for debugging.
- Uploads and results persist in the `canal_storage` volume.

Stop with `Ctrl+C`, or run detached with `docker compose up --build -d` and stop with `docker compose down`.

The included `best_binary_unet_v5.pth` scores open canal channel pixels. The
included `canal_lines.pt` refines a centreline near the supplied or bundled
alignment. Keep both in `backend/app/config/models/`; the line model is not the
blockage scorer. Restart the backend after replacing either model.

## Run without Docker (development)

Backend:
```
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Frontend (separate terminal):
```
cd frontend
npm install
npm run dev        # http://localhost:5173  (proxies /api to :8000)
```

## The fixed models
The app auto-detects the blockage scorer in `backend/app/config/models/`; pin
its exact name with `CANAL_MODEL_FILE` and set `CANAL_MODEL_VERSION` for display.
The optional centreline model uses `CANAL_LINE_MODEL` (default
`canal_lines.pt`) and can be disabled with `CANAL_REFINE=0`.

## Build status
- [x] Step 1, fixed-model setup + upload UI (no model dropdown)
- [x] Step 2, blockage prediction + optional canal-line refinement
- [x] Step 3, optional silt (DSM - DTM: per-reach depth, class, and volume)
- [x] Step 4, results map, per-reach imagery & downloads
- [x] Step 5, interactive chain view (clickable reach boxes -> zoom image + lat/long JSON) + UI polish
- [x] Durable job records, refresh recovery, and shareable `?job=<id>` result URLs
- [x] GeoTIFF and DSM/DTM validation, visible analysis errors
