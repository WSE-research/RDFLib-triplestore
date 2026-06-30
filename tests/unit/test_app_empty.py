"""Tests against the app as shipped: the bundled data/ directory holds only a
README, so the data catalog is empty and only the utility routes are mounted."""
import importlib
import sys

from fastapi.testclient import TestClient


def _fresh_app():
    sys.modules.pop("app", None)
    return importlib.import_module("app")


def test_catalog_is_empty_without_graph_dirs():
    app_module = _fresh_app()
    assert app_module.data_catalog == {}


def test_root_redirects_to_health():
    client = TestClient(_fresh_app().app)
    resp = client.get("/", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["location"] == "/health"


def test_favicon_redirects():
    client = TestClient(_fresh_app().app)
    resp = client.get("/favicon.ico", follow_redirects=False)
    assert resp.status_code == 302
    assert "RDFlib.png" in resp.headers["location"]


def test_health_empty_catalog():
    client = TestClient(_fresh_app().app)
    resp = client.get("/health/")
    assert resp.status_code == 200
    assert resp.json() == {}
