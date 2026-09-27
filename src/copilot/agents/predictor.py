"""Call the optional prediction tool without coupling ML availability to legal assessment.

Expected missing-model or coverage outcomes become warnings. The graph still
returns its rules assessment and any supported claim draft.
"""

from collections.abc import Callable

from copilot.graph.state import CopilotState
from copilot.ml.predict import PredictionUnavailableError, predict_delay


def predictor_agent(state: CopilotState, predictor: Callable = predict_delay) -> dict:
    """Preserve provenance and treat model failure as loss of optional context only."""
    warnings = list(state.get("warnings", []))
    prediction = None
    try:
        prediction = predictor(
            state["request"].disruption.flight,
            allow_synthetic=state["request"].allow_synthetic_prediction,
        )
        warnings.extend(prediction.limitations)
    except PredictionUnavailableError as exc:
        warnings.append(str(exc))
    except Exception:
        warnings.append("Delay prediction failed; the rules assessment is unaffected.")
    return {"prediction": prediction, "warnings": warnings, "steps": state["steps"] + ["predictor"]}
