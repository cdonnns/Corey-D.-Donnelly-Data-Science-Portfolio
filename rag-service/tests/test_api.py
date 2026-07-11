"""
Integration tests hit the real FastAPI app but with RAG_MOCK_LLM=true so
they run fully offline and deterministically in CI -- no API keys, no
flakiness from network calls, no per-PR API spend.
"""
import os

os.environ["RAG_MOCK_LLM"] = "true"

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("RAG_VECTOR_INDEX_PATH", str(tmp_path / "index"))
    from app.main import app

    with TestClient(app) as c:
        yield c


def test_liveness(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "alive"


def test_readiness(client):
    r = client.get("/readyz")
    assert r.status_code == 200


def test_metrics_endpoint_exposes_prometheus_format(client):
    r = client.get("/metrics")
    assert r.status_code == 200
    assert b"rag_requests_total" in r.content


def test_query_rejects_empty_string(client):
    r = client.post("/v1/query", json={"query": ""})
    assert r.status_code == 422


def test_query_rejects_bad_top_k(client):
    r = client.post("/v1/query", json={"query": "hello", "top_k": 50})
    assert r.status_code == 422


def test_feedback_logs_successfully(client):
    r = client.post(
        "/v1/feedback",
        json={"query_id": "abc123", "rating": 4, "comment": "pretty good"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "logged"
