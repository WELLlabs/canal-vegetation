"""Golden-patch tests: same RGB/alpha/px_m → same mask as notebook 04."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from src.tiling import CLASS_BG, iter_blocks, linearity_filter, make_mask, vari

FIXTURE = Path(__file__).parent / "fixtures" / "golden_patch.npz"


def _synthetic_patch(size: int = 128) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Bright grey linear canal on a vegetated field — same construction every run."""
    r = np.full((size, size), 40.0, dtype=np.float32)
    g = np.full((size, size), 90.0, dtype=np.float32)
    b = np.full((size, size), 30.0, dtype=np.float32)
    alpha = np.full((size, size), 255.0, dtype=np.float32)
    r[:, 50:70] = 180.0
    g[:, 50:70] = 178.0
    b[:, 50:70] = 176.0
    alpha[:8, :] = 0
    return r, g, b, alpha


class TestVari(unittest.TestCase):
    def test_vari_formula(self):
        r = np.array([[100.0]])
        g = np.array([[150.0]])
        b = np.array([[50.0]])
        expected = (150.0 - 100.0) / (150.0 + 100.0 - 50.0)
        np.testing.assert_allclose(vari(r, g, b), [[expected]])


class TestLinearityFilter(unittest.TestCase):
    def test_drops_compact_blob(self):
        mask = np.zeros((40, 40), dtype=bool)
        mask[10:18, 10:18] = True
        out = linearity_filter(mask, min_aspect=2.5)
        self.assertFalse(out.any())

    def test_keeps_elongated_strip(self):
        mask = np.zeros((40, 40), dtype=bool)
        mask[18:22, 2:38] = True
        out = linearity_filter(mask, min_aspect=2.5)
        self.assertGreater(out.sum(), 0)


class TestMakeMaskGolden(unittest.TestCase):
    def test_deterministic(self):
        r, g, b, a = _synthetic_patch()
        m1 = make_mask(r, g, b, a, 0.0462)
        m2 = make_mask(r, g, b, a, 0.0462)
        np.testing.assert_array_equal(m1, m2)

    def test_matches_fixture(self):
        r, g, b, a = _synthetic_patch()
        mask = make_mask(r, g, b, a, 0.0462)
        self.assertTrue(FIXTURE.exists(), f"Missing golden fixture {FIXTURE}")
        gold = np.load(FIXTURE)
        np.testing.assert_array_equal(gold["r"], r)
        np.testing.assert_array_equal(gold["g"], g)
        np.testing.assert_array_equal(gold["b"], b)
        np.testing.assert_array_equal(gold["alpha"], a)
        np.testing.assert_array_equal(gold["mask"], mask)
        self.assertGreater((mask > CLASS_BG).sum(), 0)

    def test_nodata_is_background(self):
        r, g, b, a = _synthetic_patch()
        mask = make_mask(r, g, b, a, 0.0462)
        self.assertTrue(np.all(mask[:8, :] == CLASS_BG))


class TestBlockTiler(unittest.TestCase):
    def test_grid(self):
        tiles = list(iter_blocks(1024, 1024, patch_size=512, stride=256))
        self.assertEqual(len(tiles), 9)
        self.assertEqual(tiles[0].col, 0)
        self.assertEqual(tiles[0].row, 0)
        self.assertEqual(tiles[-1].col, 512)
        self.assertEqual(tiles[-1].row, 512)


if __name__ == "__main__":
    unittest.main()
