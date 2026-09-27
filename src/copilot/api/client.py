"""Keep HTTP details out of the teaching UI and validate every server response."""

import os

import httpx

from copilot.api.status import ModelStatus
from copilot.schemas.flight import CopilotResponse
from copilot.schemas.requests import CopilotRequest


def assess_remote(request: CopilotRequest) -> CopilotResponse:
    """Call the locally configured service once; retries could repeat costly provider calls."""
    url = os.getenv("COPILOT_API_URL", "http://127.0.0.1:8000").rstrip("/")
    try:
        response = httpx.post(f"{url}/assess", json=request.model_dump(mode="json"), timeout=90)
        response.raise_for_status()
        return CopilotResponse.model_validate(response.json())
    except (httpx.HTTPError, ValueError):
        return CopilotResponse(
            status="error",
            warnings=[
                "Unable to get an assessment. Check that the API is running "
                "and try again. No result was saved for this submission."
            ],
        )


def fetch_model_status() -> ModelStatus:
    """Display an honest unknown state if the service is unavailable, never a guessed source."""
    url = os.getenv("COPILOT_API_URL", "http://127.0.0.1:8000").rstrip("/")
    try:
        response = httpx.get(f"{url}/model-status", timeout=3)
        response.raise_for_status()
        return ModelStatus.model_validate(response.json())
    except (httpx.HTTPError, ValueError):
        return ModelStatus(message="Model data source unavailable: check that the API is running.")
