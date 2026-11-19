"""Canal Blockage App - FastAPI backend (Step 2: real blockage inference).

Prediction runs in a background thread so large orthophotos never block the
request. Job state and progress are polled from the frontend. Results (per-reach
JSON, GeoJSON, summary) are written under storage/results/<job_id>/.
"""
from __future__ import annotations
import shutil, uuid, datetime, threading, traceback, json, io, csv, re, os
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, Response

from . import config, model_registry, alignments, regions
from .pipeline import runner, geo, refine

app = FastAPI(title="Canal Blockage App", version="0.2.0")
app.add_middleware(CORSMiddleware, allow_origins=config.CORS_ORIGINS + ["*"],
                   allow_methods=["*"], allow_headers=["*"])

JOBS: dict[str, dict] = {}
_LOCK = threading.Lock()


def _job_file(job_id: str) -> Path:
    if not re.fullmatch(r"[a-f0-9]{12}", job_id):
        raise HTTPException(404, "Job not found.")
    return config.RESULTS_DIR / job_id / "job.json"


def _job_dir(job_id: str) -> Path:
    return _job_file(job_id).parent


def _save_job(job_id: str):
    path = _job_file(job_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(JOBS[job_id], default=str))
    os.replace(tmp, path)


def _now():
    return datetime.datetime.utcnow().isoformat() + "Z"


def _set(job_id, **kw):
    with _LOCK:
        JOBS[job_id].update(**kw)
        _save_job(job_id)


def _worker(job_id: str, align_path: Path, ortho_path: Path, out_dir: Path,
            canal_key="", canal_label="", default_width=6.0, default_ctype="",
            clip_layer=False, dsm_path=None, dtm_path=None):
    try:
        _set(job_id, state="loading_model", progress=2, message="Loading model")
        model = model_registry.load_segmenter(device=config.DEVICE)

        # For large layers (state or national), clip to the orthophoto footprint
        # so only the local canal(s) are read and cut.
        bbox = None
        if clip_layer:
            _set(job_id, progress=4, message=f"Finding canal under the orthophoto ({canal_label or 'canal layer'})")
            layer_crs = geo.read_prj_crs(Path(align_path))
            bbox = geo.footprint_bbox_in_crs(str(ortho_path), layer_crs, pad_m=300.0)

        # Search a wide band around the alignment for the canal actually visible in the
        # orthophoto and move the line onto it, so the narrow scoring strip sits on the canal.
        refine_info = {"refined": False}
        line_prob_path = None
        if refine.available():
            _set(job_id, state="running", progress=5,
                 message="Searching for the canal around the alignment")
            try:
                new_path, line_prob_path, refine_info = refine.refine_alignment(
                    str(ortho_path), align_path, clip_layer, out_dir,
                    progress=lambda p, m: _set(job_id, progress=int(p), message=m))
            except Exception as exc:          # never block scoring on this step
                new_path, line_prob_path = None, None
                refine_info = {"refined": False,
                               "note": f"refinement failed, original alignment used: {exc}"}
            if new_path is not None:
                align_path, bbox = new_path, None
            elif refine_info.get("no_visible_canal"):
                # Do not fall back to the raw shapefile — that is what painted
                # roads and village traces as blocked canals.
                message = refine_info.get("note") or (
                    "Mapped canal lines under this orthophoto are not visible in the imagery.")
                summary = {
                    "canal": canal_key, "canal_label": canal_label,
                    "total_reaches": 0, "covered_reaches": 0,
                    "distribution": {"clear": 0, "partial": 0, "moderate": 0, "blocked": 0},
                    "overlap": False, "message": message,
                    "alignment_refinement": refine_info,
                }
                out_dir = Path(out_dir)
                out_dir.mkdir(parents=True, exist_ok=True)
                (out_dir / "summary.json").write_text(json.dumps(summary, indent=2))
                (out_dir / "results.json").write_text("[]")
                (out_dir / "reaches.geojson").write_text(
                    json.dumps({"type": "FeatureCollection", "features": []}))
                (out_dir / "boxes.json").write_text(
                    json.dumps({"tile": canal_label, "width": 1, "height": 1, "boxes": []}))
                _set(job_id, state="completed", progress=100, message="Completed",
                     summary=summary, finished_at=_now())
                return
        else:
            refine_info["note"] = ("refinement switched off (CANAL_REFINE=0)" if not config.REFINE_ENABLED
                                   else f"line model {config.LINE_MODEL_FILE} not installed in "
                                        "config/models; original alignment used")

        _set(job_id, state="running", progress=15, message="Segmenting reaches")

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
            line_prob_path=str(line_prob_path) if line_prob_path else None,
            line_conf_min=config.LINE_CONF_MIN,
        )
        summary["alignment_refinement"] = refine_info
        (Path(out_dir) / "summary.json").write_text(json.dumps(summary, indent=2))
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
    info = model_registry.model_info()
    info["alignment_refinement"] = {
        "installed": refine.available(),
        "name": config.LINE_MODEL_FILE if refine.available() else None,
    }
    info["canal_layers"] = {
        "regions": regions.list_regions(),
        "national": Path(config.NATIONAL_CANALS_SHP).exists(),
    }
    return info


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

    By default the canal is auto-selected from a matching state centreline
    (Karnataka first) or the bundled national layer, clipped to the orthophoto
    footprint, so the user uploads only the orthophoto.
    An optional uploaded ``alignment`` (zipped shapefile or GeoJSON) overrides it;
    the bundled ``canal`` key is still accepted for backward compatibility.
    """
    if not orthophoto.filename or Path(orthophoto.filename).suffix.lower() not in {".tif", ".tiff"}:
        raise HTTPException(400, "Orthophoto must be a GeoTIFF (.tif or .tiff).")
    if bool(dsm) != bool(dtm):
        raise HTTPException(400, "Silt analysis needs both a DSM and a DTM.")
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
    try:
        import rasterio
        with rasterio.open(ortho_path) as raster:
            if raster.crs is None:
                raise HTTPException(400, "Orthophoto has no coordinate reference system (CRS).")
            if raster.count < 3:
                raise HTTPException(400, "Orthophoto must contain at least three RGB bands.")
            if raster.width < 2 or raster.height < 2:
                raise HTTPException(400, "Orthophoto contains no usable image area.")
    except HTTPException:
        shutil.rmtree(up_dir, ignore_errors=True)
        raise
    except Exception as exc:
        shutil.rmtree(up_dir, ignore_errors=True)
        raise HTTPException(400, f"Could not read the uploaded GeoTIFF: {exc}") from exc

    for label, raster_file in (("DSM", dsm), ("DTM", dtm)):
        if raster_file is None:
            continue
        if not raster_file.filename or Path(raster_file.filename).suffix.lower() not in {".tif", ".tiff"}:
            shutil.rmtree(up_dir, ignore_errors=True)
            raise HTTPException(400, f"{label} must be a GeoTIFF (.tif or .tiff).")
        path = _save(raster_file, f"{label.lower()}.tif")
        try:
            import rasterio
            with rasterio.open(path) as raster:
                if raster.crs is None or raster.count < 1:
                    raise HTTPException(400, f"{label} needs a CRS and at least one elevation band.")
        except HTTPException:
            shutil.rmtree(up_dir, ignore_errors=True)
            raise
        except Exception as exc:
            shutil.rmtree(up_dir, ignore_errors=True)
            raise HTTPException(400, f"Could not read the uploaded {label}: {exc}") from exc

    # Resolve the reach source. Priority: uploaded alignment > bundled canal key
    # > matching state centreline > national layer.
    canal_key = canal or ""
    canal_label = ""
    default_width, default_ctype = 6.0, ""
    clip_layer = False
    if alignment is not None and alignment.filename:
        ext = Path(alignment.filename).suffix.lower()
        if ext not in _ALIGN_EXTS - {".shp"}:
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
        region = regions.pick_for_orthophoto(ortho_path)
        if region:
            align_path = region["path"]
            canal_key = region["key"]
            canal_label = region["label"]
            default_width = region["width"]
            default_ctype = region["ctype"]
            clip_layer = True
            source = "region"
        elif Path(config.NATIONAL_CANALS_SHP).exists():
            align_path = config.NATIONAL_CANALS_SHP
            canal_label = "Auto-selected from the national canal layer"
            clip_layer = True
            source = "national"
        else:
            raise HTTPException(
                500, "No canal layer is installed. Drop a Karnataka shapefile in "
                     "backend/app/assets/regions/karnataka/ or install the national layer.")

    dsm_path = up_dir / "dsm.tif" if dsm is not None else None
    dtm_path = up_dir / "dtm.tif" if dtm is not None else None
    want_silt = bool(dsm_path and dtm_path)

    with _LOCK:
        JOBS[job_id] = {
            "id": job_id, "canal": canal_key, "canal_label": canal_label,
            "source": source, "state": "queued", "progress": 0,
            "message": "Queued", "want_silt": want_silt,
            "silt_note": (None if want_silt else "Upload both DSM and DTM to include silt analysis."),
            "created_at": _now(),
        }
        _save_job(job_id)
    threading.Thread(
        target=_worker,
        args=(job_id, align_path, ortho_path, out_dir),
        kwargs=dict(canal_key=canal_key, canal_label=canal_label,
                    default_width=default_width, default_ctype=default_ctype,
                    clip_layer=clip_layer, dsm_path=dsm_path, dtm_path=dtm_path),
        daemon=True).start()
    return JSONResponse(JOBS[job_id], status_code=202)


@app.get("/api/jobs/{job_id}")
def job(job_id: str):
    record_path = _job_file(job_id)
    if job_id not in JOBS:
        if not record_path.exists():
            raise HTTPException(404, "Job not found.")
        try:
            record = json.loads(record_path.read_text())
            if record.get("state") in {"queued", "loading_model", "running"}:
                record.update(state="failed", error="The server restarted before this analysis finished.",
                              finished_at=_now())
                record_path.write_text(json.dumps(record))
            elif record.get("state") == "completed":
                summary_path = record_path.parent / "summary.json"
                if summary_path.exists():
                    record["summary"] = json.loads(summary_path.read_text())
            JOBS[job_id] = record
        except Exception as exc:
            raise HTTPException(500, "Could not restore this job record.") from exc
    return JOBS[job_id]


@app.get("/api/jobs/{job_id}/results")
def results(job_id: str):
    f = _job_dir(job_id) / "results.json"
    if not f.exists():
        raise HTTPException(404, "Results not ready.")
    return FileResponse(f, media_type="application/json")


@app.get("/api/jobs/{job_id}/geojson")
def geojson(job_id: str):
    f = _job_dir(job_id) / "reaches.geojson"
    if not f.exists():
        raise HTTPException(404, "GeoJSON not ready.")
    return FileResponse(f, media_type="application/geo+json")


@app.get("/api/jobs/{job_id}/csv")
def csv_export(job_id: str):
    f = _job_dir(job_id) / "results.json"
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
    f = _job_dir(job_id) / "reaches" / f"{rid}.jpg"
    if not f.exists():
        raise HTTPException(404, "No image for this reach.")
    return FileResponse(f, media_type="image/jpeg")


@app.get("/api/jobs/{job_id}/overview")
def overview(job_id: str):
    f = _job_dir(job_id) / "overview.png"
    if not f.exists():
        raise HTTPException(404, "No overview for this job.")
    return FileResponse(f, media_type="image/png")


@app.get("/api/jobs/{job_id}/boxes")
def boxes(job_id: str):
    f = _job_dir(job_id) / "boxes.json"
    if not f.exists():
        raise HTTPException(404, "No boxes for this job.")
    return FileResponse(f, media_type="application/json")
