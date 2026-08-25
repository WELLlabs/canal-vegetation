"""
E2E verification mirroring the frontend api/analyzeImage.ts + pipeline.ts flow.
Uses validated real-data windows (not full mosaics).
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import httpx

BASE = "http://127.0.0.1:8000/api/v1"
ROOT = Path(__file__).resolve().parents[1]
VAL = ROOT / "data" / "validation"
ALIGN_DIR = Path(r"D:\Github\Canal Pipeline\gis\TLBC_D95")
POLL_S = 2.0
TIMEOUT = httpx.Timeout(600.0, connect=30.0)


def poll_job(client: httpx.Client, job_id: str) -> dict:
    while True:
        r = client.get(f"{BASE}/jobs/{job_id}")
        r.raise_for_status()
        body = r.json()
        status = body["status"]
        print(f"  job {job_id[:8]}… {status} {body.get('progress')}% {body.get('message') or body.get('current_stage')}")
        if status in ("completed", "failed"):
            return body
        time.sleep(POLL_S)


def run_case(name: str, ortho: Path, alignment_files: list[Path] | None = None) -> dict:
    print(f"\n=== {name} ===")
    with httpx.Client(timeout=TIMEOUT) as client:
        # 1. create project
        pr = client.post(f"{BASE}/projects", json={"name": f"e2e-{name}"})
        pr.raise_for_status()
        project_id = pr.json()["project_id"]
        print("project", project_id)

        # 2. start prediction
        files = [("ortho_file", (ortho.name, ortho.read_bytes(), "image/tiff"))]
        if alignment_files:
            for p in alignment_files:
                files.append(("alignment_files", (p.name, p.read_bytes(), "application/octet-stream")))
        up = client.post(f"{BASE}/projects/{project_id}/predictions", files=files)
        up.raise_for_status()
        job = up.json()
        print("queued", job["job_id"], "prediction", job.get("prediction_id"))

        # 3. poll
        final = poll_job(client, job["job_id"])
        if final["status"] == "failed":
            raise RuntimeError(final.get("error") or final.get("message") or "failed")

        pred_id = final.get("prediction_id") or job.get("prediction_id")
        assert pred_id

        # 4. prediction details
        det = client.get(f"{BASE}/predictions/{pred_id}")
        det.raise_for_status()
        payload = det.json()

        # 5. canonical geojson
        gj = client.get(f"{BASE}/predictions/{pred_id}/geojson")
        gj.raise_for_status()
        geojson = gj.json()

        features = geojson.get("features") or []
        thumbs_ok = []
        for feat in features[:5]:
            rel = (feat.get("properties") or {}).get("thumbnail_relpath") or ""
            if not rel:
                thumbs_ok.append(False)
                continue
            name_only = rel.replace("images/", "")
            img = client.get(f"{BASE}/predictions/{pred_id}/images/{name_only}")
            thumbs_ok.append(img.status_code == 200 and len(img.content) > 100)

        out = {
            "case": name,
            "project_id": project_id,
            "job_id": job["job_id"],
            "prediction_id": pred_id,
            "job_status": final["status"],
            "pipeline_mode": payload.get("pipeline_mode") or geojson.get("metadata", {}).get("pipeline_mode"),
            "model_version": payload.get("model_version") or geojson.get("metadata", {}).get("model_version"),
            "summary": payload.get("summary"),
            "n_features": len(features),
            "sample_props": [f.get("properties") for f in features[:3]],
            "thumbnails_ok": thumbs_ok,
            "geojson_type": geojson.get("type"),
            "has_metadata": bool(geojson.get("metadata")),
        }
        print(json.dumps({k: out[k] for k in ("case", "pipeline_mode", "n_features", "summary", "thumbnails_ok")}, indent=2))
        return out


def main() -> int:
    health = httpx.get("http://127.0.0.1:8000/health", timeout=10.0)
    health.raise_for_status()
    print("health", health.json())

    results = []
    results.append(run_case("ortho_only", VAL / "attanur4_real_window.tif"))

    align = [
        ALIGN_DIR / "TLBC_D95.shp",
        ALIGN_DIR / "TLBC_D95.shx",
        ALIGN_DIR / "TLBC_D95.dbf",
        ALIGN_DIR / "TLBC_D95.prj",
    ]
    for p in align:
        if not p.is_file():
            raise FileNotFoundError(p)
    results.append(run_case("ortho_plus_alignment", VAL / "shakapur_real_window.tif", align))

    out_path = VAL / "phase1_frontend_e2e.json"
    out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print("wrote", out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
