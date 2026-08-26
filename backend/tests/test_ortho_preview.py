"""Ortho preview export + API route."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))


class TestOrthoPreviewExport(unittest.TestCase):
    def test_write_preview_and_bounds(self):
        import rasterio
        from rasterio.transform import from_origin
        from app.pipeline.export.ortho_preview import write_ortho_preview

        with tempfile.TemporaryDirectory() as tmp:
            tif = Path(tmp) / "ortho.tif"
            data = np.full((3, 256, 384), 90, np.uint8)
            transform = from_origin(722000, 1794000, 0.5, 0.5)
            with rasterio.open(
                tif,
                "w",
                driver="GTiff",
                height=256,
                width=384,
                count=3,
                dtype="uint8",
                crs="EPSG:32643",
                transform=transform,
            ) as dst:
                dst.write(data)
            dest = Path(tmp) / "ortho_preview.jpg"
            meta = write_ortho_preview(tif, dest, long_edge=512)
            self.assertTrue(dest.is_file())
            self.assertGreater(dest.stat().st_size, 100)
            south, west = meta["ortho_bounds"][0]
            north, east = meta["ortho_bounds"][1]
            self.assertLess(south, north)
            self.assertLess(west, east)
            # Lon/lat for India UTM 43N
            self.assertTrue(70 < west < 80)
            self.assertTrue(10 < south < 25)


try:
    from fastapi.testclient import TestClient
    from app.main import app
except ModuleNotFoundError:
    TestClient = None
    app = None


@unittest.skipIf(TestClient is None, "fastapi not installed")
class TestOrthoRoute(unittest.TestCase):
    def test_ortho_route_404_unknown(self):
        client = TestClient(app)
        res = client.get("/api/v1/predictions/does-not-exist/ortho")
        self.assertEqual(res.status_code, 404)


if __name__ == "__main__":
    unittest.main()
