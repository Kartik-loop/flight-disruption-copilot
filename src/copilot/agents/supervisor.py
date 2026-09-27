"""Route between specialists using explicit progress instead of an unconstrained LLM loop.

Each specialist runs at most once per request. Follow-up answers are submitted
as a new request with corrected structured facts; no database or checkpoint
service is needed for this phase.
"""

from copilot.agents.drafter import can_draft
from copilot.graph.state import CopilotState, NodeName


def supervisor_agent(state: CopilotState) -> dict:
    """Choose the next useful specialist and terminate when intake cannot proceed."""
    steps, request = state["steps"], state["request"]
    # LEARN: The routing policy is deterministic because these dependencies are
    # known: facts precede rules, and assessed remedies precede drafting. Asking
    # an LLM to select the next step would add cost without improving this policy.
    if state.get("error"):
        next_node = "finalize"
    elif "intake" not in steps:
        next_node = "intake"
    elif request.disruption is None:
        next_node = "finalize"
    elif "eligibility" not in steps:
        next_node = "eligibility"
    elif request.want_prediction and "predictor" not in steps:
        next_node = "predictor"
    elif (
        request.want_letter
        and "drafter" not in steps
        and any(can_draft(result) for result in state["assessments"])
    ):
        next_node = "drafter"
    else:
        next_node = "finalize"
    return {"next_node": next_node}


def route_from_supervisor(state: CopilotState) -> NodeName:
    """Expose the selected node to LangGraph's conditional edge."""
    return state["next_node"]
