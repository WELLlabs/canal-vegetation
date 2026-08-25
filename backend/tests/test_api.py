"""API smoke tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    from fastapi.testclient import TestClient
    from app.main import app
except ModuleNotFoundError:
    TestClient = None
    app = None


@unittest.skipIf(TestClient is None, "fastapi not installed")
class TestHealth(unittest.TestCase):
    def test_health(self):
        client = TestClient(app)
        res = client.get("/health")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json(), {"status": "healthy"})


@unittest.skipIf(TestClient is None, "fastapi not installed")
class TestProjectsAndJobs(unittest.TestCase):
    def test_create_project_and_missing_job(self):
        client = TestClient(app)
        res = client.post("/api/v1/projects", json={"name": "Phase1"})
        self.assertEqual(res.status_code, 200)
        self.assertIn("project_id", res.json())
        missing = client.get("/api/v1/jobs/does-not-exist")
        self.assertEqual(missing.status_code, 404)


if __name__ == "__main__":
    unittest.main()
