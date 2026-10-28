import os
from pathlib import Path
APP_DIR = Path(__file__).resolve().parent
BACKEND_DIR = APP_DIR.parent
ASSETS_DIR = APP_DIR / "assets"
ALIGN_DIR = ASSETS_DIR / "alignments"
# Bundled pan-India canal network. The app auto-selects the canal(s) under the
# uploaded orthophoto from this layer, so the user does not upload a shapefile.
NATIONAL_CANALS_SHP = Path(
    os.getenv("CANAL_NATIONAL_SHP", str(ASSETS_DIR / "national" / "Canal.shp")))
MODELS_DIR = APP_DIR / "config" / "models"
STORAGE_DIR = APP_DIR / "storage"
UPLOADS_DIR = STORAGE_DIR / "uploads"
RESULTS_DIR = STORAGE_DIR / "results"
for _p in (MODELS_DIR, UPLOADS_DIR, RESULTS_DIR):
    _p.mkdir(parents=True, exist_ok=True)
FIXED_MODEL_FILENAME = os.getenv("CANAL_MODEL_FILE", "").strip()
MODEL_VERSION = os.getenv("CANAL_MODEL_VERSION", "v5").strip()
REACH_LENGTH_M = 50
CORS_ORIGINS = os.getenv("CANAL_CORS", "http://localhost:5173").split(",")
DEVICE = os.getenv("CANAL_DEVICE", "cpu").strip()
