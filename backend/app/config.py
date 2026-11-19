import os
from pathlib import Path
APP_DIR = Path(__file__).resolve().parent
BACKEND_DIR = APP_DIR.parent
ASSETS_DIR = APP_DIR / "assets"
ALIGN_DIR = ASSETS_DIR / "alignments"
# State / region centrelines. Drop a shapefile into regions/<state>/; the app
# uses it when the orthophoto falls inside that layer. Add the next state in
# regions.py, then put its files in the matching folder.
REGIONS_DIR = ASSETS_DIR / "regions"
# Bundled pan-India canal network. Used when no matching state layer is installed
# (or the image is outside every installed state).
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

# --- Alignment refinement (search for the canal around the alignment before scoring) ---
# Model trained by the Colab notebook (canal_extraction_unet_v2, <work_dir>/model.pt), copied into
# config/models/ under this name. If the file is missing, refinement is skipped.
LINE_MODEL_FILE = os.getenv("CANAL_LINE_MODEL", "canal_lines.pt").strip()
REFINE_ENABLED = os.getenv("CANAL_REFINE", "1").strip() != "0"
# How far either side of the alignment to search for the canal (metres). The scoring strip itself
# stays narrow (the reach width); this only widens where the canal is LOOKED FOR.
SEARCH_M = float(os.getenv("CANAL_SEARCH_M", "80"))
REFINE_PARAMS = dict(
    buffer_m=SEARCH_M,
    corridor_m=min(40.0, SEARCH_M / 2),
    retry_corridor_m=max(SEARCH_M - 5, 0),
    tta=os.getenv("CANAL_REFINE_TTA", "0").strip() == "1",   # 4x slower on CPU; small gain
    batch=8, amp=False,
)
# Reaches whose line runs where the line model sees less canal probability than this (0-1) are
# marked "no_canal" (road, bund, field edge, or canal hidden under trees) instead of "blocked".
LINE_CONF_MIN = float(os.getenv("CANAL_LINE_CONF_MIN", "0.3"))
