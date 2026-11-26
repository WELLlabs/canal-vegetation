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
    # Line acceptance (same rule as the Karnataka notebook). A traced line is scored only if
    # mean probability >= min_mean_prob AND at least min_coverage of its pixels reach
    # pixel_prob_threshold. Rejected lines are kept for display, never scored.
    min_mean_prob=float(os.getenv("CANAL_LINE_MIN_MEAN_PROB", "0.5")),
    min_coverage=float(os.getenv("CANAL_LINE_MIN_COVERAGE", "0.6")),
    pixel_prob_threshold=float(os.getenv("CANAL_LINE_PIXEL_PROB", "0.5")),
)
# Per-reach check, after the whole-line filter above. Reaches whose line runs where the line model sees less canal probability than this (0-1) are
# marked "no_canal" (road, bund, field edge, or canal hidden under trees) instead of "blocked".
LINE_CONF_MIN = float(os.getenv("CANAL_LINE_CONF_MIN", "0.3"))

# --- Reach scoring ---
# "vegetation" (default): the core repo's / client's method, blockage = vegetation cover of the
# canal strip, classed by VEG_THRESHOLDS (0-5 clear, 6-40 partial, 41-70 moderate, 71-100 blocked).
# "open_water": the old v5 U-Net rule (blockage = 1 - open water share). It reads every dry or
# earthen canal as blocked, so it is kept only for comparison.
SCORING_METHOD = os.getenv("CANAL_SCORING", "vegetation").strip().lower()
VEG_THRESHOLDS = tuple(int(x) for x in os.getenv("CANAL_VEG_THRESHOLDS", "5,40,70").split(","))
# Optional trained classifier from the core repo (bala_rewrite/training.py output). If this file
# is in config/models/, its 3-class prediction sets each reach's class; vegetation cover stays
# the blockage per cent.
BLOCKAGE_CLASSIFIER_FILE = os.getenv("CANAL_BLOCKAGE_CLASSIFIER", "vegetation_blockage_model.pkl").strip()
