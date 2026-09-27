"""Exercise the HTTP boundary with real rules and sanitized failures, without provider calls."""

import json
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("langgraph")
from fastapi.testclient import TestClient

from copilot.api.main import app


def test_assessment_and_health():
    """The public endpoint must preserve the workflow's award and disclaimer."""
    with TestClient(app) as client:
        example = json.loads(Path("examples/eu_delay.json").read_text())
        response = client.post("/assess", json={"disruption": example})
        assert response.status_code == 200
        assert response.json()["eligibility"]["compensation_amount"] == 250
        assert "This is not legal advice" in response.json()["disclaimer"]
        assert client.get("/health").json()["status"] == "ok"


@pytest.mark.parametrize("payload", [{}, {"text": ""}, {"text": "private", "unknown": 1}])
def test_invalid_input(payload):
    """Invalid bodies must not leak user input in validation messages."""
    response = TestClient(app).post("/assess", json=payload)
    assert response.status_code == 422
    assert response.json()["status"] == "error"
    assert "private" not in response.text
    assert "This is not legal advice" in response.text


def test_unexpected_failure(monkeypatch):
    """Even unexpected failures should return a safe response rather than provider secrets."""

    def fail(request):
        """Stand in for a dependency failing with sensitive diagnostic text."""
        raise RuntimeError("secret-provider-token")

    monkeypatch.setattr("copilot.api.main.run_copilot", fail)
    response = TestClient(app, raise_server_exceptions=False).post("/assess", json={"text": "hi"})
    assert response.status_code == 500
    assert "secret-provider-token" not in response.text
    assert "This is not legal advice" in response.text


def test_unknown_airport_requests_review():
    """A syntactically valid but unknown airport must not become a made-up distance or award."""
    case = json.loads(Path("examples/eu_delay.json").read_text())
    case["flight"]["departure_airport"] = "ZZZ"
    response = TestClient(app).post("/assess", json={"disruption": case})
    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "review_required"
    assert body["eligibility"]["eligible"] is None
    assert body["claim_letter"] is None


def test_no_provider_key_error(monkeypatch):
    """Ensure empty provider settings produce actionable advice through HTTP."""
    from copilot.config import Settings

    monkeypatch.setattr(
        "copilot.agents.llm.get_settings",
        lambda: Settings(
            _env_file=None, openai_api_key=None, google_api_key=None, llm_provider="openai"
        ),
    )
    response = TestClient(app).post("/assess", json={"text": "My flight was late"})
    assert response.status_code == 200
    assert response.json()["status"] == "error"
    assert "No API key" in response.json()["warnings"][0]
    assert response.json()["claim_letter"] is None
