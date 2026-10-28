"""Canal Blockage App - FastAPI backend (Step 2: real blockage inference).

Prediction runs in a background thread so large orthophotos never block the
request. Job state and progress are polled from the frontend. Results (per-reach
JSON, GeoJSON, summary) are written under storage/results/<job_id>/.
"""
from __future__ import annotations
import shutil, uuid, datetime, threading, traceback, json, io, csv
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, Response

from . import config, model_registry, alignments
from .pipeline import runner, geo

app = FastAPI(title="Canal Blockage App", version="0.2.0")
app.add_middleware(CORSMiddleware, allow_origins=config.CORS_ORIGINS + ["*"],
                   allow_methods=["*"], allow_headers=["*"])

JOBS: dict[str, dict] = {}
_LOCK = threading.Lock()


def _now():
    return datetime.datetime.utcnow().isoformat() + "Z"


def _set(job_id, **kw):
    with _LOCK:
        JOBS[job_id].update(**kw)


def _worker(job_id: str, align_path: Path, ortho_path: Path, out_dir: Path,
            canal_key="", canal_label="", default_width=6.0, default_ctype="",
            national=False, dsm_path=None, dtm_path=None):
    try:
        _set(job_id, state="loading_model", progress=2, message="Loading model")
        model = model_registry.load_segmenter(device=config.DEVICE)

        # For the national layer, clip to the orthophoto footprint so only the
        # local canal(s) are read and cut, not the whole country.
        bbox = None
        if national:
            _set(job_id, progress=4, message="Finding canal under the orthophoto")
            nat_crs = geo.read_prj_crs(Path(align_path))
            bbox = geo.footprint_bbox_in_crs(str(ortho_path), nat_crs, pad_m=300.0)

        _set(job_id, state="running", progress=5, message="Segmenting reaches")

        def cb(p, m):
            _set(job_id, progress=int(p), message=m)

        summary = runner.run_blockage(
            ortho_path=str(ortho_path),
            shp_path=str(align_path),
            model=model, out_dir=str(out_dir), device=config.DEVICE,
            progress_cb=cb, canal_key=canal_key, canal_label=canal_label,
            dsm_path=str(dsm_path) if dsm_path else None,
            dtm_path=str(dtm_path) if dtm_path else None,
            default_width=float(default_width), default_ctype=default_ctype,
            bbox=bbox,
        )
        _set(job_id, state="completed", progress=100, message="Completed",
             summary=summary, finished_at=_now())
    except Exception as exc:
        _set(job_id, state="failed", error=str(exc),
             trace=traceback.format_exc()[-1500:], finished_at=_now())


@app.get("/api/health")
def health():
    return {"status": "ok", "time": _now()}


@app.get("/api/model")
def model():
    return model_registry.model_info()


@app.get("/api/canals")
def canals():
    return {"canals": alignments.list_canals()}


_ALIGN_EXTS = {".zip", ".geojson", ".json", ".shp"}


@app.post("/api/predict")
async def predict(orthophoto: UploadFile = File(...),
                  alignment: UploadFile | None = File(None),
                  canal: str | None = Form(None),
                  dsm: UploadFile | None = File(None),
                  dtm: UploadFile | None = File(None)):
    """Score canal blockage on any orthophoto.

    By default the canal is auto-selected from the bundled national canal layer,
    clipped to the orthophoto footprint, so the user uploads only the orthophoto.
    An optional uploaded ``alignment`` (zipped shapefile or GeoJSON) overrides it;
    the bundled ``canal`` key is still accepted for backward compatibility.
    """
    if not model_registry.model_info().get("installed"):
        raise HTTPException(409, "No approved model is installed yet.")

    job_id = uuid.uuid4().hex[:12]
    up_dir = config.UPLOADS_DIR / job_id
    up_dir.mkdir(parents=True, exist_ok=True)
    out_dir = config.RESULTS_DIR / job_id

    def _save(f, name):
        if f is None:
            return None
        dest = up_dir / name
        with dest.open("wb") as out:
            shutil.copyfileobj(f.file, out)
        return dest

    ortho_path = _save(orthophoto, "orthophoto.tif")

    # Resolve the reach source. Priority: uploaded alignment > bundled canal key
    # > national layer (default, auto-clipped to the orthophoto).
    canal_key = canal or ""
    canal_label = ""
    default_width, default_ctype = 6.0, ""
    national = False
    if alignment is not None and alignment.filename:
        ext = Path(alignment.filename).suffix.lower()
        if ext not in _ALIGN_EXTS:
            raise HTTPException(
                400, "Alignment must be a zipped shapefile (.zip) or a GeoJSON "
                     "(.geojson / .json).")
        align_path = _save(alignment, f"alignment{ext}")
        canal_label = Path(alignment.filename).stem
        source = "uploaded"
    elif canal_key and canal_key in alignments.CANALS:
        c = alignments.CANALS[canal_key]
        align_path = alignments.shapefile_path(canal_key)
        canal_label = c["label"]
        default_width = float(c.get("width", 6.0))
        default_ctype = c.get("ctype", "")
        source = "bundled"
    else:
        if not Path(config.NATIONAL_CANALS_SHP).exists():
            raise HTTPException(
                500, "National canal layer is not installed on the server.")
        align_path = config.NATIONAL_CANALS_SHP
        canal_label = "Auto-selected from the national canal layer"
        national = True
        source = "national"

    dsm_path = _save(dsm, "dsm.tif") if dsm is not None else None
    dtm_path = _save(dtm, "dtm.tif") if dtm is not None else None
    want_silt = bool(dsm_path and dtm_path)

    with _LOCK:
        JOBS[job_id] = {
            "id": job_id, "canal": canal_key, "canal_label": canal_label,
            "source": source, "state": "queued", "progress": 0,
            "message": "Queued", "want_silt": want_silt,
            "silt_note": ("Silt analysis arrives in Step 3." if want_silt else None),
            "created_at": _now(),
        }
    threading.Thread(
        target=_worker,
        args=(job_id, align_path, ortho_path, out_dir),
        kwargs=dict(canal_key=canal_key, canal_label=canal_label,
                    default_width=default_width, default_ctype=default_ctype,
                    national=national, dsm_path=dsm_path, dtm_path=dtm_path),
        daemon=True).start()
    return JSONResponse(JOBS[job_id], status_code=202)


@app.get("/api/jobs/{job_id}")
def job(job_id: str):
    if job_id not in JOBS:
        raise HTTPException(404, "Job not found.")
    return JOBS[job_id]


@app.get("/api/jobs/{job_id}/results")
def results(job_id: str):
    f = config.RESULTS_DIR / job_id / "results.json"
    if not f.exists():
        raise HTTPException(404, "Results not ready.")
    return FileResponse(f, media_type="application/json")


@app.get("/api/jobs/{job_id}/geojson")
def geojson(job_id: str):
    f = config.RESULTS_DIR / job_id / "reaches.geojson"
    if not f.exists():
        raise HTTPException(404, "GeoJSON not ready.")
    return FileResponse(f, media_type="application/geo+json")


@app.get("/api/jobs/{job_id}/csv")
def csv_export(job_id: str):
    f = config.RESULTS_DIR / job_id / "results.json"
    if not f.exists():
        raise HTTPException(404, "Results not ready.")
    rows = json.loads(f.read_text())
    cols = ["id", "canal", "ctype", "chainage", "width", "status", "blockpct",
            "openpct", "vegpct", "silt_class", "silt_mean_m", "silt_vol_m3",
            "lon", "lat"]
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore")
    w.writeheader()
    for r in rows:
        w.writerow(r)
    return Response(buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition":
                             f'attachment; filename="{job_id}_reaches.csv"'})


@app.get("/api/jobs/{job_id}/reach/{rid}/image")
def reach_image(job_id: str, rid: int):
    f = config.RESULTS_DIR / job_id / "reaches" / f"{rid}.jpg"
    if not f.exists():
        raise HTTPException(404, "No image for this reach.")
    return FileResponse(f, media_type="image/jpeg")


@app.get("/api/jobs/{job_id}/overview")
def overview(job_id: str):
    f = config.RESULTS_DIR / job_id / "overview.png"
    if not f.exists():
        raise HTTPException(404, "No overview for this job.")
    return FileResponse(f, media_type="image/png")


@app.get("/api/jobs/{job_id}/boxes")
def boxes(job_id: str):
    f = config.RESULTS_DIR / job_id / "boxes.json"
    if not f.exists():
        raise HTTPException(404, "No boxes for this job.")
    return FileResponse(f, media_type="application/json")
