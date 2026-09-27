"""Run the Streamlit script as a user would, keeping HTTP and paid providers offline."""

import json
from pathlib import Path

import pytest

pytest.importorskip("streamlit")
pytest.importorskip("langgraph")
from streamlit.testing.v1 import AppTest

from copilot.api.status import ModelStatus
from copilot.graph.workflow import run_copilot
from copilot.schemas.flight import CopilotResponse, DelayPrediction


def test_form_result_and_stale_clear(monkeypatch):
    """A valid form reaches real rules, and a later invalid form removes its old award."""
    monkeypatch.setattr("copilot.api.client.assess_remote", run_copilot)
    app = AppTest.from_file(Path("ui/app.py").resolve()).run()
    assert any("REAL BTS DATA" in info.value for info in app.info)
    for key, value in {
        "airline": "LH",
        "departure_airport": "FRA",
        "arrival_airport": "CDG",
        "flight_date": "2025-03-10",
        "arrival_delay_minutes": "240",
        "airline_reason": "Technical fault",
    }.items():
        app.text_input(key=key).set_value(value)
    app.button[0].click().run()
    assert not app.exception
    assert app.session_state.result.eligibility.compensation_amount == 250
    app.text_input(key="flight_date").set_value("invalid")
    app.button[0].click().run()
    assert not app.exception
    assert app.error
    assert "result" not in app.session_state


def test_followup_prefill_and_synthetic_label(monkeypatch):
    """Extracted facts must survive switching input modes, and demo predictions stay labelled."""
    facts = json.loads(Path("examples/eu_delay.json").read_text())
    result = CopilotResponse(
        status="needs_information",
        collected_facts=facts,
        questions=["What was the arrival delay?"],
        delay_prediction=DelayPrediction(
            probability_delayed=0.4, risk_level="medium", features_used={}, data_source="synthetic"
        ),
    )
    monkeypatch.setattr("copilot.api.client.assess_remote", lambda request: result)
    app = AppTest.from_file(Path("ui/app.py").resolve()).run()
    app.radio(key="mode").set_value("Describe what happened").run()
    app.text_area[0].set_value("My flight was late")
    app.button[0].click().run()
    assert not app.exception
    assert any("SYNTHETIC" in warning.value for warning in app.warning)
    app.button[1].click().run()
    assert not app.exception
    assert app.text_input(key="departure_airport").value == "FRA"
    assert app.text_input(key="flight_date").value == "2025-03-10"
    assert app.selectbox(key="is_eu_carrier").value == "Not sure"


@pytest.fixture(autouse=True)
def offline_model_status(monkeypatch):
    """Keep UI tests independent of a running API while showing its source contract."""
    monkeypatch.setattr(
        "copilot.api.client.fetch_model_status",
        lambda: ModelStatus(
            available=True, data_source="bts", message="REAL BTS DATA — historical sample."
        ),
    )


def test_synthetic_banner_visible_before_submission(monkeypatch):
    """A restyle must not hide the active synthetic source until a prediction is requested."""
    monkeypatch.setattr(
        "copilot.api.client.fetch_model_status",
        lambda: ModelStatus(
            available=True,
            data_source="synthetic",
            message="SYNTHETIC DEMO ONLY — not real-world flight risk.",
        ),
    )
    app = AppTest.from_file(Path("ui/app.py").resolve()).run()
    assert not app.exception
    assert any("SYNTHETIC DEMO ONLY" in warning.value for warning in app.warning)
    assert any("This is not legal advice" in caption.value for caption in app.caption)
