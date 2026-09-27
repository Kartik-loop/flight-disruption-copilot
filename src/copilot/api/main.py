"""Expose the existing workflow over HTTP without duplicating rules or creating LLMs at startup."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from copilot.api.status import ModelStatus, model_status
from copilot.graph.workflow import run_copilot
from copilot.schemas.flight import DISCLAIMER, CopilotResponse
from copilot.schemas.requests import CopilotRequest

app = FastAPI(title="Flight Disruption Copilot", version="0.1.0", description=DISCLAIMER)


def error_response(message: str, status_code: int) -> JSONResponse:
    """Keep failures readable by the same client while hiding submitted facts and secrets."""
    body = CopilotResponse(status="error", warnings=[message])
    return JSONResponse(body.model_dump(mode="json"), status_code=status_code)


@app.exception_handler(RequestValidationError)
async def invalid_request(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Exclude raw validation inputs, which can contain a passenger's private description."""
    return error_response(
        "Invalid request. Check the field types and supply exactly one input mode.", 422
    )


@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException) -> JSONResponse:
    """Give routing errors the same disclaimer and response shape as assessments."""
    return error_response("This address or request method is not supported.", exc.status_code)


@app.exception_handler(Exception)
async def unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    """Avoid exposing provider details or tracebacks through the public response."""
    return error_response("The assessment could not be completed. Please try again.", 500)


@app.get("/health")
def health() -> dict[str, str]:
    """Report process health without spending tokens or claiming providers are configured."""
    return {"status": "ok", "disclaimer": DISCLAIMER}


@app.post("/assess", response_model=CopilotResponse)
def assess(request: CopilotRequest) -> CopilotResponse:
    """Use the same validated workflow as the CLI so interfaces cannot disagree on rules."""
    # LEARN: A normal def runs in FastAPI's worker thread pool. Our workflow uses
    # blocking provider calls, so async def would otherwise block the event loop.
    # Domain statuses such as needs_information are successful HTTP responses.
    return run_copilot(request)


@app.get("/model-status", response_model=ModelStatus)
def saved_model_status() -> ModelStatus:
    """Let the UI show data provenance before the passenger requests a prediction."""
    return model_status()
