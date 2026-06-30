"""End-to-end smoke test: the FastAPI triplestore app boots and serves health."""
import importlib
import sys

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.e2e


def test_app_boots_and_serves_health():
    sys.modules.pop("app", None)
    app_module = importlib.import_module("app")
    with TestClient(app_module.app) as client:
        resp = client.get("/health/")
        assert resp.status_code == 200
        # the root redirects into the health route
        root = client.get("/", follow_redirects=False)
        assert root.status_code == 302
