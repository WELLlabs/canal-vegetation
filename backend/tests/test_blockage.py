"""Tests for blockage scoring (notebook 07)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.blockage import score_reach


class TestScoreReach(unittest.TestCase):
    def test_clear(self):
        feats = {
            "veg_frac": 0.02,
            "silt_like_frac": 0.01,
            "gray_std": 10.0,
            "water_frac": 0.5,
        }
        out = score_reach(feats, blocked_frac=0.0)
        self.assertEqual(out["status"], "clear")

    def test_blocked_by_vegetation(self):
        feats = {
            "veg_frac": 0.6,
            "silt_like_frac": 0.0,
            "gray_std": 10.0,
            "water_frac": 0.0,
        }
        out = score_reach(feats, blocked_frac=0.0)
        self.assertEqual(out["status"], "blocked")
        self.assertIn("heavy_vegetation", out["blockage_types"])

    def test_partial_by_centerline(self):
        feats = {
            "veg_frac": 0.0,
            "silt_like_frac": 0.0,
            "gray_std": 10.0,
            "water_frac": 0.0,
        }
        out = score_reach(feats, blocked_frac=0.2)
        self.assertEqual(out["status"], "partial")


if __name__ == "__main__":
    unittest.main()
