"""Tests that exercise the data-loading loop and SPARQL router mounting by
importing the app from a temp working directory that contains a real graph."""
import importlib
import json
import os
import sys

import pytest
from fastapi.testclient import TestClient

SAMPLE_TTL = """@prefix ex: <http://example.org/> .
ex:subject ex:predicate ex:object .
ex:alice ex:name "Alice" .
"""

META = {
    "title": "Sample graph",
    "description": "A tiny graph for tests",
    "version": "1.0",
    "example_query": "SELECT * WHERE {?s ?p ?o}",
}


@pytest.fixture
def loaded_app(tmp_path, monkeypatch):
    graph_dir = tmp_path / "data" / "sample"
    graph_dir.mkdir(parents=True)
    (graph_dir / "graph.ttl").write_text(SAMPLE_TTL, encoding="utf-8")
    (graph_dir / "meta.json").write_text(json.dumps(META))
    monkeypatch.chdir(tmp_path)

    # make the app module importable from its real location
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    monkeypatch.syspath_prepend(repo_root)

    sys.modules.pop("app", None)
    return importlib.import_module("app")


def test_catalog_loads_graph_and_metadata(loaded_app):
    catalog = loaded_app.data_catalog
    assert "sample" in catalog
    entry = catalog["sample"]
    # the turtle file was parsed into a non-empty graph
    assert len(entry[loaded_app.GRAPH]) == 2
    # the meta.json was picked up
    assert entry[loaded_app.META_DATA]["title"] == "Sample graph"
    # internal/external endpoints were registered
    assert entry[loaded_app.EXTERNAL_ENDPOINT].endswith("/sample")


def test_health_reports_loaded_graph(loaded_app):
    client = TestClient(loaded_app.app)
    health = client.get("/health/").json()
    assert "sample" in health
    sample = health["sample"]
    assert sample[loaded_app.DATA][loaded_app.STATUS] == loaded_app.OK_MESSAGE
    assert sample[loaded_app.DATA][loaded_app.SIZE] == 2
    # external accessibility check fails (no live server) -> KO, exercising the
    # exception branch of the healthcheck
    assert sample[loaded_app.EXTERNAL_ENDPOINT][loaded_app.EXTERN_STATUS] == loaded_app.NOT_OK_MESSAGE


def test_sparql_endpoint_answers_select(loaded_app):
    client = TestClient(loaded_app.app)
    resp = client.get(
        "/sample",
        params={"query": "SELECT * WHERE {?s ?p ?o}"},
        headers={"accept": "application/sparql-results+json"},
    )
    assert resp.status_code == 200
    bindings = resp.json()["results"]["bindings"]
    assert len(bindings) == 2
