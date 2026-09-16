# v2 — Step-by-step build plan (backend + frontend)

_Decisions locked in `08_v2_plan.md`: any image; auto-match bundled alignment by overlap else user draws the canal **line** (or uploads a shapefile); score to the **client's verified method** (clear/partial/moderate/full at 5/40/70 %, blockage = vegetation %, structural-damage flag, thin/moderate/heavy silt, CSV schema); satellite map + ortho overlay + coloured chainage line + reach lightbox; long jobs run in the **background with email-on-done**. Report layout + result persistence = deferred._

## Milestones (ship in this order)
- **M1 — Any-image core:** draw-a-line path + client-aligned scoring + satellite map/overlay/lightbox + CSV/GeoJSON. (Backend B1–B4, Frontend F0–F3, threaded jobs.)
- **M2 — Auto-match + shapefile:** overlap auto-match of bundled alignments + shapefile-upload path.
- **M3 — Durable background + email:** worker + job store + email-on-done + results-by-URL.
- **M4 — Report + persistence:** PDF from the real layout + project-management save. _(deferred)_

---

## BACKEND

### B1 — Two-step flow: prepare → run
- **`POST /api/uploads`** (ortho, optional dsm/dtm): stream to storage; open with rasterio; return `{upload_id, crs, ortho_bounds_wgs84:[[S,W],[N,E]], px_size_m, has_dsm_dtm}`. Also kick off the **ortho preview** (downsampled ~2048 px RGB → `ortho_preview.jpg`) so the map can show imagery immediately.
- **Auto-match** (M2): intersect the ortho footprint with each bundled alignment's bbox/geometry → `matched_alignment` (key + overlapping-reach count) or `needs_geometry:true`. Return in the upload response.
- **`POST /api/jobs`**: body `{upload_id, source: "alignment"|"drawn"|"shapefile", alignment_key?, geometry_geojson?, canal_type?("main"|"distributary"), want_silt}`. Validates, creates a job row, enqueues, returns `{job_id, state:"queued"}`.

### B2 — Geometry normalisation (`pipeline/geometry.py`)
1. Resolve the source to an **ordered centreline** in the ortho CRS:
   - `drawn`: GeoJSON LineString (WGS84) → reproject to ortho CRS.
   - `shapefile`: read; if line use directly, if polygon skeletonise+order (relative chainage).
   - `alignment`: the bundled reaches (already ordered, carry chainage/width).
2. **Reach cutting:** densify the line (~2 m samples), split into **50 m reaches**; accumulate **chainage** (0 = first vertex).
3. **Corridor width:** from `canal_type` (main ±7 m / distributary ±2.5 m) or per-reach `width` if a shapefile supplies it.

### B3 — Scoring, aligned to the client (`pipeline/score.py`)
Per reach, read the ortho window along the reach; build the corridor mask (buffer ½ width):
- **Channel mask:** run the **canal-detection UNet** (`best_binary_unet_v5_lines.pth`) in the window → the channel pixels inside the corridor (this is the blockage denominator; the model's only job is finding the canal).
- **Blockage:** `blockpct = vegetation pixels ÷ channel pixels × 100`, vegetation = green **and** rough-textured (reuse `veg_fraction`). Class by **5/40/70** → `clear/partial/moderate/full`.
- **Structural damage:** per-reach roughness/brightness/low-saturation/non-green/non-water score; after all reaches, set threshold = **95th percentile (floor 0.04)**, flag exceedances → `damage = "Structural damage"`.
- **Silt** (if DSM+DTM): CHM = DSM−DTM within the channel; bands **thin <0.5 / moderate 0.5–1.0 / heavy >1.0 m**; per-reach class + volume.
- **Coordinates:** reach centroid → WGS84 `lon,lat`.

### B4 — Outputs (`pipeline/exports.py`)
- **`images/NNNN.jpg`** per reach — zoomed close-up with the red centreline drawn (matches the reference deliverable).
- **`reaches.geojson`** (WGS84 LineStrings + all props) with `metadata.ortho_bounds`, `metadata.ortho_preview`.
- **`index.csv` / `index.json`** — exact schema: `id,area,canal,type,chainage_m,status,blockpct,damage,lon,lat,image`.
- **`overview.png`** (chain) + **`ortho_preview.jpg`**.
- **`summary.json`** — 4-class distribution, damage count, silt summary, coverage.
- **Endpoints:** `GET /jobs/{id}`, `/results`, `/geojson`, `/csv`, `/reach/{rid}/image`, `/overview`, `/boxes`, **`/ortho`** (preview), plus `metadata.ortho_bounds` for the overlay.

### B5 — Background jobs + email (M3)
- **Worker:** Celery (or RQ) + Redis in `docker-compose`; job state persisted in **SQLite/Postgres** (survives tab close + restart). Progress written to the job row; polling unchanged.
- **Email:** on completion, if the job carries an email (logged-in user or entered address), send via SMTP/SES: "Analysis complete — view results" linking to `…/results/{job_id}`. Creds via env.
- **Results by URL:** `GET /results/{job_id}` rehydrates a finished job so the email link works after the tab is closed. (Full per-user persistence = project-management module, deferred; jobs keyed by id + optional email is enough for the link.)

### B6 — Model + deps + config
- torch/torchvision (CPU wheels), segmentation-models-pytorch; load **lines** model, keep v5 as fallback. GPU optional (CPU works, slow — see `05` for scale).
- Central config: class thresholds (5/40/70), corridor widths (14/5 m), silt bands (0.5/1.0), damage percentile (95, floor 0.04), reach length (50 m).

---

## FRONTEND

### F0 — Map foundation (satellite + ortho overlay + draw)
- Base = **satellite** (MapLibre GL + satellite raster, or Leaflet + Esri World Imagery). Add **maplibre-gl-draw** (or Leaflet-Geoman) for line drawing.
- Ortho overlay from `ortho_bounds` + `/ortho` preview; **Drone / Satellite** toggle.

### F1 — New upload → prepare → run flow (no canal selector)
1. **Choose imagery** (ortho + optional DSM/DTM); pick silt if both present.
2. **Prepare** (`POST /uploads`): show the ortho on the satellite map at its real location.
   - **Matched** bundled alignment → banner "Matched TLBC D95" → enable **Run**.
   - **No match** → prompt: *trace the canal centreline* or *upload a shapefile*; show canal-type (main/distributary) selector.
3. **Run** (`POST /jobs`) → processing view.

### F2 — Draw-the-line tool (F for fallback)
- Line-draw mode over the georeferenced ortho: click to add vertices, double-click/Enter to finish, undo last, redraw. Capture as WGS84 GeoJSON. Canal-type radio (sets corridor width). Hint: "start at the junction for true chainage."

### F3 — Results (satellite map + chainage line + lightbox)
- One map: satellite + ortho toggle + **chainage line coloured clear/partial/moderate/full** + click reach → **fullscreen lightbox** (close-up image, coordinates, chainage, blockpct, **damage**, silt, filmstrip ‹ ›).
- **Stat tiles:** reaches, 4-class distribution, **damage count**, silt volume. **Downloads:** CSV (client schema), GeoJSON. (PDF later.)

### F4 — Long-job UX + email
- Processing view (upload %, then phases). When a job is long, show "You can close this tab — we'll email you when it's done"; capture/confirm email. Deep-link `…/results/{job_id}` rehydrates a finished job.

### F5 — PDF (deferred)
- "Download report (PDF)" wired once the real layout is set; in-app pdf.js viewer.

---

## Validation (accuracy gate before shipping M1)
- Run v2 on the overlapping tiles (ATTANUR_2/3, SHAKAPUR) with the bundled alignment and **compare per-reach `status` against `index.csv`** (the client's field-verified labels): report exact-match %, clear↔blocked serious-error %, and the confusion matrix, matching the report's evaluation. This proves the client-aligned scoring reproduces their verified numbers.
- Keep the golden-patch test for `make_mask` (from `06`).

## Open items to confirm as we build
- Email transport (SMTP vs SES) + who the job's email belongs to (ties to auth / project-management — deferred).
- GPU vs CPU for the detection pass on large orthos (speed only).
- Report layout + result persistence — separate sessions.