# Canal Blockage App

Standalone web app for canal blockage (and optional silt) analysis from drone
orthophotos. Built on the WELL Labs canal-vegetation-model reference pipeline.

- One **fixed** approved model (no model selection anywhere).
- **Bundled** canal alignments (TLBC D95 - Attanur, NRBC), user only uploads imagery.
- Blockage + silt need **no GPU / no PyTorch** (silt is DSM-DTM; blockage is a light model).

## Layout
```
backend/   FastAPI + inference (Python)
  app/config/models/   <-- drop the ONE approved trained file here (.pkl/.joblib/.pth)
  app/assets/alignments/  bundled TLBC + NRBC reaches
frontend/  React + Vite + Tailwind + MapLibre
```

## Run with Docker (recommended)

Everything (Python, PyTorch CPU, GDAL/rasterio, the built frontend) is baked into
two images. The approved model is mounted from `backend/app/config/models/`, so it
is never copied into the image and can be swapped without a rebuild.

```
# from the canal-blockage-app/ folder
docker compose up --build
```

Then open http://localhost:8080

- Frontend (nginx) serves the UI and proxies `/api` to the backend, so there are no CORS issues and no size cap on orthophoto uploads.
- Backend API is also exposed on http://localhost:8000 for debugging.
- Uploads and results persist in the `canal_storage` volume.

Stop with `Ctrl+C`, or run detached with `docker compose up --build -d` and stop with `docker compose down`.

To swap the fixed model: replace the `.pth` in `backend/app/config/models/`, then `docker compose restart backend`.

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

## The fixed model
Place your single approved file in `backend/app/config/models/`. The app
auto-detects the one file present; pin an exact name with the `CANAL_MODEL_FILE`
env var and set `CANAL_MODEL_VERSION` for display. Blockage inference runs in Step 2.

## Build status
- [x] Step 1, fixed-model setup + upload UI (no model dropdown)
- [ ] Step 2, blockage prediction
- [x] Step 3, optional silt (DSM - DTM: per-reach depth, class, and volume)
- [x] Step 4, results map, per-reach imagery & downloads
- [x] Step 5, interactive chain view (clickable reach boxes -> zoom image + lat/long JSON) + UI polish
