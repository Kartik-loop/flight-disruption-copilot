"""The eligibility specialist delegates all decisions and explanations to pure rules.

Keeping this node small makes the separation visible: the LLM supplies facts,
but neither it nor the delay model may change an amount or legal conclusion.
"""

from copilot.graph.state import CopilotState
from copilot.rules.engine import evaluate_all_regimes


def eligibility_agent(state: CopilotState) -> dict:
    """Preserve each regime's result and questions instead of merging unlike remedies."""
    results = evaluate_all_regimes(state["request"].disruption)
    questions = list(dict.fromkeys(q for result in results for q in result.missing_information))
    return {
        "assessments": results,
        "questions": questions,
        "steps": state["steps"] + ["eligibility"],
    }
