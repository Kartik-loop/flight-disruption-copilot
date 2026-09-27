"""
tests/test_dot.py — Comprehensive unit tests for US DOT rules engine (14 CFR Part 250 & 260).

WHAT: Tests Involuntary Denied Boarding tiers (14 CFR Part 250) and automatic refund
      protections for cancellations and significant delays (14 CFR Part 260).
WHY:  Verifies that US rules are strictly implemented without inventing non-existent
      cash compensation for delays.
"""

from datetime import date

import pytest

from copilot.rules.dot import (
    DOT_DBC_CAP_200_PCT,
    DOT_DBC_CAP_400_PCT,
    evaluate_dot,
)
from copilot.schemas.flight import (
    DisruptionType,
    FlightDisruption,
    FlightInfo,
)


@pytest.fixture
def us_flight_info():
    """Helper to create minimal US domestic FlightInfo."""

    def _create(dep: str = "JFK", arr: str = "LAX", airline: str = "DL"):
        return FlightInfo(
            airline=airline,
            flight_number=f"{airline}405",
            departure_airport=dep,
            arrival_airport=arr,
            flight_date=date(2025, 8, 15),
        )

    return _create


# ── Denied Boarding Tests (14 CFR Part 250) ────────────────────────────────


def test_dot_denied_boarding_under_1_hour(us_flight_info):
    """Under 14 CFR § 250.5(a)(1), alternate arrival <= 1 hour requires $0 DBC."""
    flight = us_flight_info("JFK", "LAX")
    disruption = FlightDisruption(
        flight=flight,
        disruption_type=DisruptionType.DENIED_BOARDING,
        rerouting_arrival_delay_minutes=45,  # <= 1 hour
        volunteered_seat=False,
        denied_due_to_overbooking=True,
        met_checkin_requirements=True,
        was_rerouted=True,
        one_way_fare_usd=250,
    )
    result = evaluate_dot(disruption)
    assert result.eligible is False
    assert result.compensation_amount == 0.0
    assert any("250.5(a)(1)" in r for r in result.applicable_rules)


def test_dot_denied_boarding_1_to_2_hours(us_flight_info):
    """Under 14 CFR § 250.5(a)(2), alternate arrival 1-2 hours late pays 200% (max $1,075)."""
    flight = us_flight_info("JFK", "LAX")
    disruption = FlightDisruption(
        flight=flight,
        disruption_type=DisruptionType.DENIED_BOARDING,
        rerouting_arrival_delay_minutes=90,  # 1.5 hours
        volunteered_seat=False,
        denied_due_to_overbooking=True,
        met_checkin_requirements=True,
        was_rerouted=True,
        one_way_fare_usd=250,
    )
    result = evaluate_dot(disruption)
    assert result.eligible is True
    assert result.compensation_currency == "USD"
    assert result.compensation_amount <= DOT_DBC_CAP_200_PCT
    assert any("250.5(a)(2)" in r for r in result.applicable_rules)
    assert "CASH or CHECK" in result.reasoning


def test_dot_denied_boarding_over_2_hours(us_flight_info):
    """Under 14 CFR § 250.5(a)(3), alternate arrival > 2 hours late pays 400% (max $2,150)."""
    flight = us_flight_info("ORD", "SFO")
    disruption = FlightDisruption(
        flight=flight,
        disruption_type=DisruptionType.DENIED_BOARDING,
        rerouting_arrival_delay_minutes=180,  # 3 hours
        volunteered_seat=False,
        denied_due_to_overbooking=True,
        met_checkin_requirements=True,
        was_rerouted=True,
        one_way_fare_usd=250,
    )
    result = evaluate_dot(disruption)
    assert result.eligible is True
    assert result.compensation_currency == "USD"
    assert result.compensation_amount <= DOT_DBC_CAP_400_PCT
    assert any("250.5(a)(3)" in r for r in result.applicable_rules)


def test_dot_voluntary_denied_boarding(us_flight_info):
    """Voluntary surrender does not qualify for statutory DBC under 14 CFR § 250.2b."""
    flight = us_flight_info("JFK", "MIA")
    disruption = FlightDisruption(
        flight=flight,
        disruption_type=DisruptionType.DENIED_BOARDING,
        volunteered_seat=True,
    )
    result = evaluate_dot(disruption)
    assert result.eligible is False
    assert result.compensation_amount is None
    assert any("250.2b" in r for r in result.applicable_rules)


# ── Cancellation & Refund Tests (14 CFR Part 260) ──────────────────────────


def test_dot_cancellation_gives_refund_not_cash_penalty(us_flight_info):
    """Cancellations in the US entitle passenger to full prompt refund, not cash compensation."""
    flight = us_flight_info("ATL", "DFW")
    disruption = FlightDisruption(
        flight=flight,
        disruption_type=DisruptionType.CANCELLATION,
    )
    result = evaluate_dot(disruption)
    assert result.eligible is False  # No statutory cash compensation
    assert result.compensation_amount is None
    assert "REFUND" in result.reasoning
    assert "14 CFR Part 260" in result.reasoning
    assert any("260" in r for r in result.applicable_rules)


# ── Flight Delays Under US Law ─────────────────────────────────────────────


def test_dot_delay_no_fixed_cash_compensation(us_flight_info):
    """
    US law DOES NOT mandate fixed delay compensation like EU261.
    For significant delays (>= 3h domestic), passenger gets refund right if declining travel.
    """
    flight = us_flight_info("JFK", "LAX")

    # 4-hour delay
    disruption = FlightDisruption(
        flight=flight,
        disruption_type=DisruptionType.DELAY,
        arrival_delay_minutes=240,
    )
    result = evaluate_dot(disruption)
    assert result.eligible is False  # No cash compensation
    assert result.compensation_amount is None
    assert "NO STATUTORY DELAY COMPENSATION" in result.reasoning
    assert "significant delay" in result.reasoning.lower()


def test_dot_minor_delay(us_flight_info):
    """Delay under 3 hours is not a significant delay under Part 260."""
    flight = us_flight_info("JFK", "LAX")
    disruption = FlightDisruption(
        flight=flight,
        disruption_type=DisruptionType.DELAY,
        arrival_delay_minutes=45,
    )
    result = evaluate_dot(disruption)
    assert result.eligible is False
    assert (
        "less than 3 hours" in result.reasoning.lower() or "not qualify" in result.reasoning.lower()
    )
