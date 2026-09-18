"""
tests/test_schemas.py — Unit tests for Pydantic schema validation.

WHAT: Verifies that our Pydantic models accept valid data and reject invalid data.
WHY:  Schemas are the data contracts between all agents. If a schema is wrong,
      every downstream component breaks. Testing them early catches issues before
      we build agents on top.

LEARN: Testing Pydantic models is straightforward: construct instances with
valid data and assert they work, then try invalid data and assert they raise
ValidationError. This is the simplest form of unit testing — no mocks, no
fixtures, just "given this input, expect this output."
"""

from datetime import date, datetime

import pytest
from pydantic import ValidationError

from copilot.schemas.flight import (
    CompensationResult,
    CopilotResponse,
    DelayPrediction,
    DisruptionType,
    FlightDisruption,
    FlightInfo,
    Region,
)


# ── Fixtures ─────────────────────────────────────────────────────────────
# LEARN: pytest fixtures are reusable setup functions. Any test that takes
# a parameter with the same name as a fixture automatically receives its
# return value. This avoids repeating setup code across many tests.

@pytest.fixture
def sample_flight_info() -> FlightInfo:
    """A valid FlightInfo object for reuse across tests."""
    return FlightInfo(
        airline="LH",
        flight_number="LH400",
        departure_airport="FRA",
        arrival_airport="JFK",
        scheduled_departure=datetime(2024, 6, 15, 10, 30),
        scheduled_arrival=datetime(2024, 6, 15, 14, 0),
        flight_date=date(2024, 6, 15),
    )


@pytest.fixture
def sample_disruption(sample_flight_info: FlightInfo) -> FlightDisruption:
    """A valid FlightDisruption for reuse across tests."""
    return FlightDisruption(
        flight=sample_flight_info,
        disruption_type=DisruptionType.DELAY,
        arrival_delay_minutes=200,
        airline_reason="Technical fault with the aircraft",
    )


# ── FlightInfo tests ─────────────────────────────────────────────────────

class TestFlightInfo:
    """Tests for the FlightInfo model."""

    def test_valid_creation(self, sample_flight_info: FlightInfo):
        """Valid data should produce a FlightInfo without errors."""
        assert sample_flight_info.airline == "LH"
        assert sample_flight_info.departure_airport == "FRA"
        assert sample_flight_info.arrival_airport == "JFK"

    def test_minimal_creation(self):
        """Only required fields should be needed."""
        info = FlightInfo(
            airline="UA",
            departure_airport="ORD",
            arrival_airport="LAX",
            flight_date=date(2024, 7, 1),
        )
        assert info.flight_number is None
        assert info.scheduled_departure is None

    def test_missing_required_field(self):
        """Missing required fields should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            FlightInfo(
                airline="UA",
                # departure_airport is missing!
                arrival_airport="LAX",
                flight_date=date(2024, 7, 1),
            )
        # LEARN: exc_info.value gives you the actual exception object.
        # We check that the error mentions the missing field name.
        assert "departure_airport" in str(exc_info.value)


# ── FlightDisruption tests ──────────────────────────────────────────────

class TestFlightDisruption:
    """Tests for the FlightDisruption model."""

    def test_valid_delay(self, sample_disruption: FlightDisruption):
        """A valid delay disruption should construct without errors."""
        assert sample_disruption.disruption_type == DisruptionType.DELAY
        assert sample_disruption.arrival_delay_minutes == 200

    def test_valid_cancellation(self, sample_flight_info: FlightInfo):
        """A valid cancellation disruption should construct without errors."""
        d = FlightDisruption(
            flight=sample_flight_info,
            disruption_type=DisruptionType.CANCELLATION,
            cancellation_notice_days=1,
        )
        assert d.disruption_type == DisruptionType.CANCELLATION
        assert d.cancellation_notice_days == 1

    def test_negative_delay_rejected(self, sample_flight_info: FlightInfo):
        """Negative delay minutes should be rejected (ge=0 constraint)."""
        with pytest.raises(ValidationError):
            FlightDisruption(
                flight=sample_flight_info,
                disruption_type=DisruptionType.DELAY,
                arrival_delay_minutes=-30,
            )

    def test_invalid_disruption_type(self, sample_flight_info: FlightInfo):
        """An invalid disruption type string should be rejected."""
        with pytest.raises(ValidationError):
            FlightDisruption(
                flight=sample_flight_info,
                disruption_type="turbulence",  # Not a valid enum value!
            )

    def test_enum_values(self):
        """Verify the three disruption types exist."""
        assert DisruptionType.DELAY.value == "delay"
        assert DisruptionType.CANCELLATION.value == "cancellation"
        assert DisruptionType.DENIED_BOARDING.value == "denied_boarding"


# ── CompensationResult tests ─────────────────────────────────────────────

class TestCompensationResult:
    """Tests for the CompensationResult model."""

    def test_eligible_result(self):
        """An eligible result should have compensation details."""
        result = CompensationResult(
            eligible=True,
            regulation=Region.EU,
            compensation_amount=250.0,
            compensation_currency="EUR",
            reasoning="Flight delayed 4 hours on a 1200 km route.",
            applicable_rules=["EU261 Art. 7(1)(a)"],
        )
        assert result.eligible is True
        assert result.compensation_amount == 250.0
        assert len(result.applicable_rules) == 1

    def test_ineligible_result(self):
        """An ineligible result needs only eligible=False and reasoning."""
        result = CompensationResult(
            eligible=False,
            reasoning="Flight was not covered by EU261 or DOT rules.",
        )
        assert result.eligible is False
        assert result.compensation_amount is None
        assert result.applicable_rules == []  # default_factory=list


# ── DelayPrediction tests ───────────────────────────────────────────────

class TestDelayPrediction:
    """Tests for the DelayPrediction model."""

    def test_valid_prediction(self):
        """A valid prediction should construct without errors."""
        pred = DelayPrediction(
            probability_delayed=0.35,
            risk_level="medium",
        )
        assert pred.probability_delayed == 0.35
        assert pred.features_used == {}  # default_factory=dict

    def test_probability_bounds(self):
        """Probability must be between 0 and 1."""
        with pytest.raises(ValidationError):
            DelayPrediction(probability_delayed=1.5, risk_level="high")
        with pytest.raises(ValidationError):
            DelayPrediction(probability_delayed=-0.1, risk_level="low")


# ── CopilotResponse tests ───────────────────────────────────────────────

class TestCopilotResponse:
    """Tests for the final CopilotResponse model."""

    def test_disclaimer_always_present(self, sample_disruption: FlightDisruption):
        """The disclaimer should be auto-included via default value."""
        response = CopilotResponse(disruption=sample_disruption)
        assert "not" in response.disclaimer.lower() or "DISCLAIMER" in response.disclaimer
        assert "legal advice" in response.disclaimer.lower()

    def test_full_response(self, sample_disruption: FlightDisruption):
        """A full response with all fields should construct without errors."""
        response = CopilotResponse(
            disruption=sample_disruption,
            eligibility=CompensationResult(
                eligible=True,
                regulation=Region.EU,
                compensation_amount=600.0,
                compensation_currency="EUR",
                reasoning="Long-haul delay.",
                applicable_rules=["EU261 Art. 7(1)(c)"],
            ),
            delay_prediction=DelayPrediction(
                probability_delayed=0.42,
                risk_level="medium",
            ),
            claim_letter="Dear Lufthansa, ...",
        )
        assert response.eligibility.eligible is True
        assert response.claim_letter is not None
