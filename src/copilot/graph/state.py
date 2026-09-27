"""Shared workflow state records facts and finished steps for bounded, inspectable routing.

LangGraph merges each node's returned fields into this state. Each run starts
fresh: there is no global conversation history or cross-user mutable state.
"""

from typing import Any, Literal, TypedDict

from copilot.schemas.flight import CompensationResult, CopilotResponse, DelayPrediction
from copilot.schemas.requests import CopilotRequest

NodeName = Literal["intake", "eligibility", "predictor", "drafter", "finalize"]

# TODO(next): Add request-scoped persistence only when a multi-turn UI needs it.


class CopilotState(TypedDict, total=False):
    """Describe node updates without making unfinished work look like a completed result."""

    request: CopilotRequest
    facts: dict[str, Any]
    assessments: list[CompensationResult]
    prediction: DelayPrediction | None
    letter: str | None
    questions: list[str]
    warnings: list[str]
    error: bool
    steps: list[str]
    next_node: NodeName
    response: CopilotResponse
