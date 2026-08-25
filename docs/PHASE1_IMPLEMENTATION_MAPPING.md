# Phase 1 implementation mapping

Short plan: reuse existing `backend/app/pipeline/*` for UNet + 07 postprocess/blockage/damage. Add alignment ingest/corridor/reaches, one canonical GeoJSON, project/prediction storage, and frontend map + alignment upload. Skip silt, FIC UNet, and retraining.

| Reference source | Project module | Purpose |
|------------------|----------------|---------|
| 05 UNet-ResNet50 | `backend/app/pipeline/models/canal_model.py` | Architecture + ImageNet norm + TTA helper |
| 07 tiled infer / TTA | `backend/app/pipeline/detection/canal_detection.py` | Overlapping 512 / step 384 / DS=8 mosaic |
| 07 Cell 6 FIC width filter | `backend/app/pipeline/processing/postprocessing.py` | CC + canal vs FIC-candidate |
| 07 `_build_corridor` | `backend/app/pipeline/geospatial/corridor.py` | Alignment buffer at mask resolution |
| Alignment load / CRS | `backend/app/pipeline/geospatial/alignment.py` | GeoJSON + shapefile + sidecars |
| 07 Cell 8 reaches | `backend/app/pipeline/processing/reach_analysis.py` | Ortho-only skeleton reaches |
| 07 Cell 9–10 blockage | `backend/app/pipeline/processing/blockage_scoring.py` + `detection/blockage_detection.py` | Ortho-only veg/silt-like score |
| 07 Cell 17 damage | `backend/app/pipeline/detection/blockage_detection.py` (`detect_sd`) | Ortho-only structural flag |
| `predict_segments.py` / `line_blockage.py` | `backend/app/pipeline/detection/alignment_analysis.py` | Reaches along polyline + 4-class veg % |
| `detect_damage.py` | same `alignment_analysis.py` | Rocky/rubble damage in type-width corridor |
| `box_images.py` / `tlbc_production.py` | `backend/app/pipeline/export/thumbnails.py` + `export/geojson.py` | Clickable boxes, `images/NNNN.jpg`, EPSG:4326 |
| Weight order `_lines` then `_v5` | `backend/app/pipeline/models/registry.py` | `model_version` = loaded filename |
| Job + Celery/thread | `backend/app/services/job_service.py` + `workers/tasks.py` | queued / running / completed / failed |
| Single entry | `backend/app/pipeline/run.py` | `run_prediction(...)` |

Intentionally not mapped (Phase 1 out of scope): notebooks 03/04/06/08, Water-bodies, `train_predict_v2.py`, FIC UNet runtime, DSM/DTM silt.
