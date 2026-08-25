"""Silt classification mapping from notebook 08."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.pipeline.processing.silt_classes import silt_status_from_counts


class TestSiltStatus(unittest.TestCase):
    def test_heavy_maps_to_high(self):
        self.assertEqual(silt_status_from_counts(0, 0, 30, 100), "high")

    def test_moderate_maps_to_medium(self):
        self.assertEqual(silt_status_from_counts(0, 30, 0, 100), "medium")

    def test_clear_maps_to_low(self):
        self.assertEqual(silt_status_from_counts(100, 0, 0, 100), "low")


if __name__ == "__main__":
    unittest.main()
