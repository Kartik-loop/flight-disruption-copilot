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
