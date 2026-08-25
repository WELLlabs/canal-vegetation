"""Phase 1 unit tests — no real orthomosaic accuracy claims."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))


class TestAlignmentSkipsOutOfBounds(unittest.TestCase):
    def test_no_features_outside_raster(self):
        from rasterio.crs import CRS
        from app.core.config import Settings
        from app.pipeline.detection.alignment_analysis import analyze_alignment_reaches
        from app.pipeline.geospatial.alignment import load_alignment

        window = Path(__file__).resolve().parents[1] / "data" / "validation" / "shakapur_real_window.tif"
        shp = Path(r"D:\Github\Canal Pipeline\gis\TLBC_D95\TLBC_D95.shp")
        if not window.is_file() or not shp.is_file():
            self.skipTest("real validation window or alignment shapefile not present")
        lines = load_alignment(shp, CRS.from_epsg(32643))
        reaches = analyze_alignment_reaches(str(window), lines, Settings())
        self.assertGreater(len(reaches), 0)
        self.assertLess(len(reaches), 100)
        for r in reaches:
            self.assertIsNotNone(r.get("bbox_px"))


class TestTileGrid(unittest.TestCase):
    def test_matches_notebook_range(self):
        from app.pipeline.io.raster_reader import iter_tile_offsets

        W, H, tile, step = 2000, 1600, 512, 384
        got = list(iter_tile_offsets(W, H, tile, step))
        expected = [
            (col, row)
            for row in range(0, H - tile + 1, step)
            for col in range(0, W - tile + 1, step)
        ]
        self.assertEqual(got, expected)
        self.assertEqual(len(got), ((H - tile) // step + 1) * ((W - tile) // step + 1))


class TestArchitecture(unittest.TestCase):
    def test_unet_resnet50_no_weights(self):
        from app.pipeline.models.canal_model import build_canal_unet

        m = build_canal_unet("resnet50")
        self.assertEqual(sum(p.numel() for p in m.parameters()), 32521105)


class TestModelSelection(unittest.TestCase):
    def test_prefers_lines_then_v5(self):
        from app.core.config import Settings
        from app.pipeline.models.canal_model import resolve_canal_weights

        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            v5 = d / "best_binary_unet_v5.pth"
            lines = d / "best_binary_unet_v5_lines.pth"
            v5.write_bytes(b"x")
            settings = Settings(model_dir=d, model_v5_path="", model_v5_lines_path="")
            self.assertEqual(resolve_canal_weights(settings).name, "best_binary_unet_v5.pth")
            lines.write_bytes(b"y")
            self.assertEqual(resolve_canal_weights(settings).name, "best_binary_unet_v5_lines.pth")

    def test_missing_raises(self):
        from app.core.config import Settings
        from app.core.errors import MODEL_NOT_AVAILABLE, AppError
        from app.pipeline.models.canal_model import resolve_canal_weights

        with tempfile.TemporaryDirectory() as tmp:
            settings = Settings(model_dir=Path(tmp), model_v5_path="", model_v5_lines_path="")
            with self.assertRaises(AppError) as ctx:
                resolve_canal_weights(settings)
            self.assertEqual(ctx.exception.code, MODEL_NOT_AVAILABLE)


class TestCanonicalSchema(unittest.TestCase):
    def test_status_mapping(self):
        from app.schemas.prediction import canonical_blockage_status

        self.assertEqual(canonical_blockage_status("blocked"), "full")
        self.assertEqual(canonical_blockage_status("full"), "full")
        self.assertEqual(canonical_blockage_status("partial"), "partial")
        self.assertEqual(canonical_blockage_status("clear"), "clear")
        self.assertEqual(canonical_blockage_status("moderate"), "moderate")

    def test_geojson_shape(self):
        from app.pipeline.export.geojson import canonical_collection, _feature

        feat = _feature(
            reach_id="0",
            geom={"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]},
            tile_id="tile",
            canal_name="c",
            canal_type="main",
            chainage_m=10,
            status="blocked",
            blockage_pct=80,
            structural_damage=True,
            thumbnail_relpath="images/0001.jpg",
            src_crs=None,
        )
        col = canonical_collection(
            [feat],
            project_id="p",
            prediction_id="x",
            model_version="best_binary_unet_v5.pth",
            pipeline_mode="ortho_only",
            label_source="model",
        )
        self.assertEqual(col["type"], "FeatureCollection")
        self.assertEqual(col["metadata"]["pipeline_mode"], "ortho_only")
        p = col["features"][0]["properties"]
        self.assertEqual(p["blockage_status"], "full")
        self.assertNotIn("blockpct", p)
        self.assertNotIn("struct_damage", p)
        self.assertTrue(p["thumbnail_relpath"].startswith("images/"))
        self.assertFalse(p["thumbnail_relpath"].startswith("D:"))
        self.assertFalse(p["thumbnail_relpath"].startswith("C:"))


class TestAlignmentGeoJSON(unittest.TestCase):
    def test_load_and_reproject(self):
        from rasterio.crs import CRS
        from app.pipeline.geospatial.alignment import load_alignment

        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "a.geojson"
            p.write_text(
                json.dumps(
                    {
                        "type": "FeatureCollection",
                        "features": [
                            {
                                "type": "Feature",
                                "properties": {"canal": "TLBC", "type": "main"},
                                "geometry": {
                                    "type": "LineString",
                                    "coordinates": [[77.1, 16.2], [77.11, 16.21]],
                                },
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            lines = load_alignment(p, CRS.from_epsg(32643))
            self.assertEqual(len(lines), 1)
            self.assertEqual(lines[0]["canal_type"], "main")
            self.assertGreater(lines[0]["pts_xy"][0, 0], 100000)


class TestShapefileSidecars(unittest.TestCase):
    def test_missing_sidecars(self):
        from app.core.errors import MISSING_SHAPEFILE_SIDECARS, AppError
        from app.pipeline.geospatial.alignment import validate_shapefile_sidecars

        with tempfile.TemporaryDirectory() as tmp:
            shp = Path(tmp) / "x.shp"
            shp.write_bytes(b"not-a-real-shp")
            with self.assertRaises(AppError) as ctx:
                validate_shapefile_sidecars(shp)
            self.assertEqual(ctx.exception.code, MISSING_SHAPEFILE_SIDECARS)


class TestClassifyPct(unittest.TestCase):
    def test_bins(self):
        from app.pipeline.detection.alignment_analysis import classify_blockage_pct

        self.assertEqual(classify_blockage_pct(0), "clear")
        self.assertEqual(classify_blockage_pct(20), "partial")
        self.assertEqual(classify_blockage_pct(50), "moderate")
        self.assertEqual(classify_blockage_pct(90), "full")


class TestThumbnailRelpath(unittest.TestCase):
    def test_relative_images_path(self):
        seq = 1
        rel = f"images/{seq:04d}.jpg"
        self.assertEqual(rel, "images/0001.jpg")
        self.assertFalse(rel.startswith("D:"))
        self.assertFalse(rel.startswith("C:"))


class TestCrsConversion(unittest.TestCase):
    def test_utm_polygon_to_4326(self):
        from rasterio.crs import CRS
        from app.pipeline.export.geojson import warp_geom_to_4326

        geom = {
            "type": "Polygon",
            "coordinates": [[[722000, 1794000], [722010, 1794000], [722010, 1794010], [722000, 1794010], [722000, 1794000]]],
        }
        out = warp_geom_to_4326(geom, CRS.from_epsg(32643))
        lon, lat = out["coordinates"][0][0]
        self.assertTrue(70 < lon < 85)
        self.assertTrue(10 < lat < 25)


class TestRgbRaster(unittest.TestCase):
    def test_rgb_not_rgba(self):
        import rasterio
        from rasterio.transform import from_origin
        from app.pipeline.io.raster_reader import open_meta

        with tempfile.TemporaryDirectory() as tmp:
            tif = Path(tmp) / "rgb.tif"
            data = np.full((3, 32, 32), 80, np.uint8)
            transform = from_origin(722000, 1794000, 0.05, 0.05)
            with rasterio.open(
                tif,
                "w",
                driver="GTiff",
                height=32,
                width=32,
                count=3,
                dtype="uint8",
                crs="EPSG:32643",
                transform=transform,
            ) as dst:
                dst.write(data)
            meta = open_meta(str(tif))
            self.assertEqual(meta.count, 3)


class TestJobLifecycle(unittest.TestCase):
    def test_create_queued(self):
        from app.core.config import get_settings
        from app.models.db import get_engine
        from app.services.job_service import create_job, ensure_default_project, get_job

        get_settings()
        get_engine()
        ensure_default_project()
        job = create_job("/tmp/missing.tif", project_id="default")
        loaded = get_job(job.id)
        self.assertEqual(loaded.status, "queued")
        self.assertEqual(loaded.pipeline_mode, "ortho_only")


class TestHealth(unittest.TestCase):
    def test_health(self):
        try:
            from fastapi.testclient import TestClient
            from app.main import app
        except ModuleNotFoundError:
            self.skipTest("fastapi missing")
        client = TestClient(app)
        res = client.get("/health")
        self.assertEqual(res.status_code, 200)


class TestSyntheticPipeline(unittest.TestCase):
    """Smoke test with a fake predictor — not model-accuracy validation."""

    def test_ortho_only_fake_model(self):
        import rasterio
        from rasterio.transform import from_origin
        from app.core.config import Settings
        from app.pipeline.run import run_prediction

        class FakeModel:
            model_version = "fake.pth"

            def predict_tile(self, rgb_chw):
                h, w = rgb_chw.shape[1], rgb_chw.shape[2]
                prob = np.zeros((h, w), np.float32)
                prob[:, w // 2 - 4 : w // 2 + 4] = 0.9
                return prob

        with tempfile.TemporaryDirectory() as tmp:
            tif = Path(tmp) / "tiny.tif"
            size = 512
            data = np.full((4, size, size), 80, np.uint8)
            data[3] = 255
            data[1, :, size // 2 - 4 : size // 2 + 4] = 40
            transform = from_origin(722000, 1794000, 0.0462, 0.0462)
            with rasterio.open(
                tif,
                "w",
                driver="GTiff",
                height=size,
                width=size,
                count=4,
                dtype="uint8",
                crs="EPSG:32643",
                transform=transform,
            ) as dst:
                dst.write(data)
            settings = Settings(
                project_root=Path(tmp) / "projects",
                model_dir=Path(tmp) / "models",
                data_dir=Path(tmp) / "data",
                upload_dir=Path(tmp) / "uploads",
                output_dir=Path(tmp) / "out",
                tile_size=512,
                tile_step=384,
                downscale_factor=8,
            )
            settings.ensure_dirs()
            result = run_prediction(
                str(tif),
                project_id="p1",
                prediction_id="pred1",
                settings=settings,
                canal_model=FakeModel(),
            )
            self.assertEqual(result.pipeline_mode, "ortho_only")
            self.assertEqual(result.model_version, "fake.pth")
            gj = json.loads(Path(result.geojson_path).read_text(encoding="utf-8"))
            self.assertEqual(gj["metadata"]["label_source"], "model")
            self.assertTrue(Path(result.geojson_path).is_file())
            for f in gj["features"]:
                self.assertIn(f["properties"]["blockage_status"], {"clear", "partial", "moderate", "full"})
                self.assertTrue(
                    not f["properties"]["thumbnail_relpath"]
                    or f["properties"]["thumbnail_relpath"].startswith("images/")
                )

    def test_alignment_mode_fake_model(self):
        import rasterio
        from rasterio.transform import from_origin
        from rasterio.warp import transform as warp_xy
        from app.core.config import Settings
        from app.pipeline.run import run_prediction

        class FakeModel:
            model_version = "fake.pth"

            def predict_tile(self, rgb_chw):
                h, w = rgb_chw.shape[1], rgb_chw.shape[2]
                return np.full((h, w), 0.9, np.float32)

        with tempfile.TemporaryDirectory() as tmp:
            tif = Path(tmp) / "tiny.tif"
            size = 512
            data = np.full((3, size, size), 80, np.uint8)
            transform = from_origin(722000, 1794000, 0.2, 0.2)
            with rasterio.open(
                tif,
                "w",
                driver="GTiff",
                height=size,
                width=size,
                count=3,
                dtype="uint8",
                crs="EPSG:32643",
                transform=transform,
            ) as dst:
                dst.write(data)
            xs, ys = [722010, 722090], [1793990, 1793910]
            lons, lats = warp_xy("EPSG:32643", "EPSG:4326", xs, ys)
            gj = Path(tmp) / "align.geojson"
            gj.write_text(
                json.dumps(
                    {
                        "type": "FeatureCollection",
                        "features": [
                            {
                                "type": "Feature",
                                "properties": {"canal": "TEST", "type": "main"},
                                "geometry": {
                                    "type": "LineString",
                                    "coordinates": [[float(a), float(b)] for a, b in zip(lons, lats)],
                                },
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            settings = Settings(
                project_root=Path(tmp) / "projects",
                model_dir=Path(tmp) / "models",
                data_dir=Path(tmp) / "data",
                upload_dir=Path(tmp) / "uploads",
                output_dir=Path(tmp) / "out",
                tile_size=512,
                tile_step=384,
                downscale_factor=8,
                alignment_reach_m=50,
                corridor_buffer_m=35,
            )
            settings.ensure_dirs()
            result = run_prediction(
                str(tif),
                alignment_path=str(gj),
                project_id="p1",
                prediction_id="predA",
                settings=settings,
                canal_model=FakeModel(),
            )
            self.assertEqual(result.pipeline_mode, "ortho_plus_alignment")
            col = json.loads(Path(result.geojson_path).read_text(encoding="utf-8"))
            self.assertEqual(col["metadata"]["label_source"], "rule")
            self.assertGreaterEqual(len(col["features"]), 1)


if __name__ == "__main__":
    unittest.main()
