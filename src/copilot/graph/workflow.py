"""Wire phase-4 specialists into a bounded LangGraph workflow with one typed response.

StateGraph executes real nodes and conditional edges; the supervisor records
which node should run next. Injecting the extractor and predictor lets tests
exercise the same graph without external services or API charges.

Reference: https://docs.langchain.com/oss/python/langgraph/graph-api
"""

from collections.abc import Callable
from functools import partial

from langchain_core.runnables import Runnable
from langgraph.graph import END, START, StateGraph

from copilot.agents.drafter import drafter_agent
from copilot.agents.eligibility import eligibility_agent
from copilot.agents.intake import intake_agent
from copilot.agents.predictor import predictor_agent
from copilot.agents.supervisor import route_from_supervisor, supervisor_agent
from copilot.graph.state import CopilotState
from copilot.ml.predict import predict_delay
from copilot.schemas.flight import CopilotResponse
from copilot.schemas.requests import CopilotRequest


def finalize_agent(state: CopilotState) -> dict:
    """Include a disclaimer on successful, incomplete, unsupported, and failed requests alike."""
    assessments = state.get("assessments", [])
    if state.get("error"):
        status = "error"
    elif state.get("questions"):
        status = "needs_information"
    elif any(result.review_required for result in assessments):
        status = "review_required"
    else:
        status = "complete"
    return {
        "response": CopilotResponse(
            status=status,
            disruption=state["request"].disruption,
            collected_facts=state.get("facts", {}),
            questions=state.get("questions", []),
            eligibility=assessments[0] if assessments else None,
            additional_assessments=assessments[1:],
            delay_prediction=state.get("prediction"),
            claim_letter=state.get("letter"),
            warnings=state.get("warnings", []),
            steps=state["steps"] + ["finalize"],
        )
    }


def build_workflow(extractor: Runnable | None = None, predictor: Callable = predict_delay):
    """Compile the graph without creating a provider client or loading an ML artifact."""
    builder = StateGraph(CopilotState)
    builder.add_node("supervisor", supervisor_agent)
    builder.add_node("intake", partial(intake_agent, extractor=extractor))
    builder.add_node("eligibility", eligibility_agent)
    builder.add_node("predictor", partial(predictor_agent, predictor=predictor))
    builder.add_node("drafter", drafter_agent)
    builder.add_node("finalize", finalize_agent)
    builder.add_edge(START, "supervisor")
    # LEARN: A conditional edge routes according to state instead of always
    # calling every specialist. Each node returns only changed fields; LangGraph
    # merges them. Lists are explicitly replaced, since this graph is sequential.
    builder.add_conditional_edges(
        "supervisor",
        route_from_supervisor,
        {name: name for name in ("intake", "eligibility", "predictor", "drafter", "finalize")},
    )
    for name in ("intake", "eligibility", "predictor", "drafter"):
        builder.add_edge(name, "supervisor")
    builder.add_edge("finalize", END)
    return builder.compile()


def run_copilot(
    request: CopilotRequest,
    *,
    extractor: Runnable | None = None,
    predictor: Callable = predict_delay,
) -> CopilotResponse:
    """Start with fresh state to prevent prior cases or stale drafts from leaking into a new run."""
    result = build_workflow(extractor, predictor).invoke(
        {"request": request, "steps": [], "warnings": [], "questions": []},
        config={"recursion_limit": 20},
    )
    return result["response"]
