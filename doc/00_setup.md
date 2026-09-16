# Project Setup Guide

This document explains how to set up, run, and troubleshoot the Canal Vegetation project in a local development environment.

## Overview

The project has two main services:

- Backend: FastAPI application for model loading, image processing, and results export
- Frontend: Vite + React app served through nginx in Docker

The recommended setup is Docker Compose, which runs both services together and keeps the app consistent across machines.

## Repository structure

```text
.
├── backend/
│   ├── app/
│   │   ├── config/
│   │   │   └── models/      # place the approved model file here
│   │   ├── assets/
│   │   ├── pipeline/
│   │   ├── storage/
│   │   ├── config.py
│   │   ├── main.py
│   │   └── model_registry.py
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   ├── Dockerfile
│   ├── package.json
│   ├── vite.config.js
│   └── nginx.conf
├── docker-compose.yml
├── README.md
├── doc/
└── ...
```

## Requirements

Before setting up the project, install:

- Docker Desktop or Docker Engine + Docker Compose
- Git
- Node.js 18+ and npm (for frontend-only development)
- Python 3.10+ (for backend-only development)

On macOS, Docker Desktop is the simplest option.

## Recommended setup: Docker Compose

This is the easiest and most reliable way to run the project.

### 1. Clone the repository

```bash
git clone <repo-url>
cd canal-vegetation
```

### 2. Add the approved model file

Place the trained model in the directory below before starting the stack:

```text
backend/app/config/models/
```

The app expects a single fixed model file, typically a PyTorch `.pth` or `.pt` segmentation model.

If you want to pin a specific file name, set the environment variable in Docker Compose or a local shell:

```bash
export CANAL_MODEL_FILE=my_model.pth
export CANAL_MODEL_VERSION=v5
```

The app will auto-detect a model in that folder if only one file is present.

### 3. Start the app

From the project root:

```bash
docker compose up --build
```

This starts:

- Backend on http://localhost:8000
- Frontend on http://localhost:8080

The frontend is served through nginx and proxies API calls to the backend.

### 4. Stop the app

```bash
docker compose down
```

Or, if it is running in the foreground:

```bash
Ctrl+C
```

## Local development without Docker

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

The backend will be available at:

```text
http://localhost:8000
```

### Frontend

Open a second terminal:

```bash
cd frontend
npm install
npm run dev
```

The frontend runs in development mode at:

```text
http://localhost:5173
```

The React app is configured to proxy `/api` calls to the backend on port 8000.

## Environment variables

The main configuration is defined in `backend/app/config.py` and can be overridden through the container environment.

Common values:

```bash
CANAL_DEVICE=cpu
CANAL_MODEL_VERSION=v5
CANAL_MODEL_FILE=my_model.pth
CANAL_CORS=http://localhost:5173
```

The Docker Compose file already sets the main runtime values:

```yaml
backend:
  environment:
    - CANAL_DEVICE=cpu
    - CANAL_MODEL_VERSION=v5
```

## What the app expects at runtime

Before processing a job, the backend checks whether a valid model is available.

If no model is found, the app will report that there is no approved model installed. This is expected until the trained file is placed in the model directory.

The named Docker volume `canal_storage` persists uploads and results outside the container filesystem.

## API health and endpoints

Once the backend is running, the health route is available:

```bash
curl http://localhost:8000/api/health
```

Typical backend routes include:

- `/api/health`
- `/api/model`
- `/api/canals`
- `/api/predict`
- `/api/jobs/{job_id}`
- `/api/jobs/{job_id}/results`
- `/api/jobs/{job_id}/geojson`
- `/api/jobs/{job_id}/csv`

## Common troubleshooting

### Model not found

Symptoms:

- backend reports no approved model installed
- prediction requests fail with a 409 or similar error

Fix:

```bash
ls -la backend/app/config/models/
```

Then place the correct model file in that directory and restart the backend service:

```bash
docker compose restart backend
```

### Port conflicts

If `localhost:8080` or `localhost:8000` is already in use:

- stop the conflicting process
- or change the port mapping in `docker-compose.yml`

Example:

```yaml
ports:
  - "8081:80"
```

### Frontend cannot reach backend

Check that the backend container is healthy and the frontend is configured to proxy `/api` requests correctly.

Useful checks:

```bash
docker compose ps
docker compose logs backend --tail=200
```

### Dependency issues in local Python setup

If backend Python packages fail to install, recreate the virtual environment and reinstall dependencies:

```bash
cd backend
rm -rf .venv
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### Frontend dependency issues

```bash
cd frontend
rm -rf node_modules package-lock.json
npm install
```

## Useful project commands

From the project root:

```bash
docker compose up --build

docker compose logs -f backend
docker compose logs -f frontend
docker compose down
```

## Notes

- The backend uses a fixed model setup rather than user-selected models.
- The Docker workflow is the default recommended path for local and demo use.
- Model files are intentionally mounted from the host into the container instead of being baked into the image so they can be replaced without rebuilding the full image.

## Next steps

After the app is running, the next standard tasks are:

1. confirm the trained model is in `backend/app/config/models/`
2. open the frontend at http://localhost:8080
3. upload imagery and confirm the analysis pipeline runs successfully
4. review output files in the persistent storage volume
