"""End-to-end smoke test of the real HTTP API (no LLM key needed: extraction
falls back to the structured form fields, which is the designed safe path)."""

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    from main import app
    return TestClient(app)


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_recommend_returns_traced_results(client):
    payload = {
        "category": "SC", "state": "Maharashtra", "annualIncome": 280000,
        "businessType": "tailoring", "amountRequired": 120000,
        "isNewBusiness": False, "requirement": "I need money for sewing machines",
    }
    body = client.post("/recommend", json=payload).json()
    assert body["results"], "expected at least one scheme"
    for r in body["results"]:
        assert r["trace"], "every scheme must explain its decision with a rule trace"
        assert "officialSourceUrl" in r
    assert any(r["eligible"] for r in body["results"])


def test_schemes_endpoint_lists_verified_schemes(client):
    body = client.get("/schemes").json()
    assert body["source"] in ("firestore", "local_json")
    assert body["count"] == len(body["schemes"]) > 0


def test_channel_partners_endpoint_lists_partners(client):
    body = client.get("/channel-partners").json()
    assert body["count"] == len(body["partners"]) > 0

