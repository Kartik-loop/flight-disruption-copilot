"""Check transport failures separately from workflow results so the UI can recover safely."""

import pytest

pytest.importorskip("httpx")
import httpx

from copilot.api.client import assess_remote
from copilot.schemas.flight import CopilotResponse
from copilot.schemas.requests import CopilotRequest


@pytest.mark.parametrize("failure", ["connection", "timeout", "invalid_json", "http_error"])
def test_client_failure(monkeypatch, failure):
    """Bad or unavailable servers must not leak raw errors or become successful assessments."""

    def post(*args, **kwargs):
        """Produce representative transport failures without network access."""
        if failure == "connection":
            raise httpx.ConnectError("private connection details")
        if failure == "timeout":
            raise httpx.ReadTimeout("private timeout details")
        return httpx.Response(
            500 if failure == "http_error" else 200,
            text="not json",
            request=httpx.Request("POST", "http://test/assess"),
        )

    monkeypatch.setattr(httpx, "post", post)
    result = assess_remote(CopilotRequest(text="My flight was cancelled"))
    assert result.status == "error"
    assert "private" not in str(result.warnings)
    assert "This is not legal advice" in result.disclaimer


def test_client_preserves_questions(monkeypatch):
    """An HTTP success can still need facts; preserve that domain status for the form."""
    result = CopilotResponse(status="needs_information", questions=["Which airline?"])
    monkeypatch.setattr(
        httpx,
        "post",
        lambda *args, **kwargs: httpx.Response(
            200,
            json=result.model_dump(mode="json"),
            request=httpx.Request("POST", "http://test/assess"),
        ),
    )
    assert assess_remote(CopilotRequest(text="Delayed")).questions == ["Which airline?"]


@pytest.fixture(autouse=True)
def configured_api(monkeypatch):
    """Transport tests opt into HTTP; deployments without a URL use the embedded graph."""
    monkeypatch.setenv("COPILOT_API_URL", "http://test")


def test_embedded_form_without_server(monkeypatch):
    """A single Streamlit process can evaluate a flight without any localhost API."""
    import json
    from pathlib import Path

    pytest.importorskip("langgraph")
    monkeypatch.delenv("COPILOT_API_URL", raising=False)
    request = CopilotRequest(disruption=json.loads(Path("examples/eu_delay.json").read_text()))
    result = assess_remote(request)
    assert result.status == "complete"
    assert result.eligibility.compensation_amount == 250
    assert result.claim_letter


def test_embedded_missing_model(monkeypatch, tmp_path):
    """A cloud checkout without the ignored binary must report unavailable, never real scores."""
    from copilot.api.client import fetch_model_status
    from copilot.config import Settings

    monkeypatch.delenv("COPILOT_API_URL", raising=False)
    monkeypatch.setattr(
        "copilot.api.status.get_settings", lambda: Settings(_env_file=None, models_dir=tmp_path)
    )
    assert fetch_model_status().available is False
    assert fetch_model_status().data_source == "unknown"
