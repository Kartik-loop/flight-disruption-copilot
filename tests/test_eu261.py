"""
tests/test_eu261.py — Comprehensive unit tests for EU Regulation (EC) No 261/2004 rules engine.

WHAT: Tests all statutory rules, distance bands, delay thresholds, cancellation notice periods,
      extraordinary circumstances exemptions, and territorial scope conditions.
WHY:  Verifies that the legal engine is 100% deterministic and compliant with official
      regulations and CJEU case law.
"""

from datetime import date

import pytest

from copilot.rules.eu261 import (
    classify_extraordinary_circumstances,
    evaluate_eu261,
)
from copilot.schemas.flight import (
    DisruptionType,
    FlightDisruption,
    FlightInfo,
    Region,
)


@pytest.fixture
def base_flight_info():
    """Helper to create minimal FlightInfo for tests."""
    def _create(dep: str, arr: str, airline: str = "LH"):
        return FlightInfo(
            airline=airline,
            flight_number=f"{airline}101",
            departure_airport=dep,
            arrival_airport=arr,
            flight_date=date(2024, 8, 1),
        )
    return _create


# ── Distance Band & Amount Tests ──────────────────────────────────────────

def test_short_haul_delay_threshold(base_flight_info):
    """
    Flight <= 1,500 km (FRA to LHR, ~655 km):
      - Delay < 3 hours (170 min): No compensation (Sturgeon).
      - Delay >= 3 hours (180 min): €250 compensation (Art. 7(1)(a)).
    """
    flight = base_flight_info("FRA", "LHR")

    # Delay under 3 hours -> Not eligible
    disruption_under_3h = FlightDisruption(
        flight=flight,
        disruption_type=DisruptionType.DELAY,
        arrival_delay_minutes=170,
    )
    result = evaluate_eu261(disruption_under_3h)
    assert result.eligible is False
    assert result.compensation_amount is None
    assert "180 minutes" in result.reasoning

    # Delay of exactly 3 hours (180 mins) -> €250
    disruption_3h = FlightDisruption(
        flight=flight,
        disruption_type=DisruptionType.DELAY,
        arrival_delay_minutes=180,
    )
    result = evaluate_eu261(disruption_3h)
    assert result.eligible is True
    assert result.compensation_amount == 250.0
    assert result.compensation_currency == "EUR"
    assert any("7(1)(a)" in r for r in result.applicable_rules)


def test_medium_haul_delay(base_flight_info):
    """
    Flight 1,500–3,500 km (MAD to WAW, ~2,290 km):
      - Delay >= 3 hours -> €400 (Art. 7(1)(b)).
    """
    flight = base_flight_info("MAD", "WAW")
    disruption = FlightDisruption(
        flight=flight,
        disruption_type=DisruptionType.DELAY,
        arrival_delay_minutes=240,
    )
    result = evaluate_eu261(disruption)
    assert result.eligible is True
    assert result.compensation_amount == 400.0
    assert result.compensation_currency == "EUR"
    assert any("7(1)(b)" in r for r in result.applicable_rules)


def test_long_haul_delay_and_50_percent_reduction(base_flight_info):
    """
    Flight > 3,500 km extra-EU (CDG to JFK, ~5,835 km):
      - Delay 3 to 4 hours (e.g. 210 mins): €300 (50% reduction under Art. 7(2)(c) & Sturgeon para 63).
      - Delay >= 4 hours (e.g. 270 mins): Full €600 (Art. 7(1)(c)).
    """
    flight = base_flight_info("CDG", "JFK")

    # Delay between 3h and 4h (3.5 hours) -> €300
    disruption_3_5h = FlightDisruption(
        flight=flight,
        disruption_type=DisruptionType.DELAY,
        arrival_delay_minutes=210,
    )
    res_reduced = evaluate_eu261(disruption_3_5h)
    assert res_reduced.eligible is True
    assert res_reduced.compensation_amount == 300.0
    assert any("7(2)(c)" in r for r in res_reduced.applicable_rules)

    # Delay >= 4 hours -> €600
    disruption_4_5h = FlightDisruption(
        flight=flight,
        disruption_type=DisruptionType.DELAY,
        arrival_delay_minutes=270,
    )
    res_full = evaluate_eu261(disruption_4_5h)
    assert res_full.eligible is True
    assert res_full.compensation_amount == 600.0
    assert any("7(1)(c)" in r for r in res_full.applicable_rules)


# ── Extraordinary Circumstances Tests ─────────────────────────────────────

def test_extraordinary_circumstances_weather_exempts(base_flight_info):
    """Severe weather / storm is an extraordinary circumstance under Art. 5(3)."""
    flight = base_flight_info("FRA", "LHR")
    disruption = FlightDisruption(
        flight=flight,
        disruption_type=DisruptionType.DELAY,
        arrival_delay_minutes=240,
        airline_reason="Severe thunderstorm and airport closure",
    )
    result = evaluate_eu261(disruption)
    assert result.eligible is False
    assert result.extraordinary_circumstances is True
    assert "Article 5(3)" in result.reasoning


def test_technical_defects_are_not_extraordinary(base_flight_info):
    """
    Under CJEU Wallentin-Hermann (C-549/07), technical faults do NOT qualify
    as extraordinary circumstances. Airline remains liable.
    """
    flight = base_flight_info("FRA", "LHR")
    disruption = FlightDisruption(
        flight=flight,
        disruption_type=DisruptionType.DELAY,
        arrival_delay_minutes=240,
        airline_reason="Technical defect in the aircraft engine fuel system",
    )
    result = evaluate_eu261(disruption)
    assert result.eligible is True
    assert result.compensation_amount == 250.0
    assert result.extraordinary_circumstances is False
    assert "Wallentin-Hermann" in result.reasoning


def test_crew_staffing_is_not_extraordinary(base_flight_info):
    """Crew shortages or sickness are operational issues inherent to airline activity."""
    flight = base_flight_info("FRA", "LHR")
    disruption = FlightDisruption(
        flight=flight,
        disruption_type=DisruptionType.DELAY,
        arrival_delay_minutes=200,
        airline_reason="Pilot crew timeout and staff shortage",
    )
    result = evaluate_eu261(disruption)
    assert result.eligible is True
    assert result.compensation_amount == 250.0


# ── Cancellation Tests ────────────────────────────────────────────────────

def test_cancellation_14_days_notice_no_compensation(base_flight_info):
    """Cancellation announced >= 14 days in advance requires no compensation (Art. 5(1)(c)(i))."""
    flight = base_flight_info("AMS", "BCN")
    disruption = FlightDisruption(
        flight=flight,
        disruption_type=DisruptionType.CANCELLATION,
        cancellation_notice_days=15,
    )
    result = evaluate_eu261(disruption)
    assert result.eligible is False
    assert result.compensation_amount is None
    assert "two weeks" in result.reasoning.lower() or "14 days" in result.reasoning.lower()


def test_cancellation_short_notice_eligible(base_flight_info):
    """Cancellation announced < 14 days in advance qualifies for Art. 7 compensation."""
    flight = base_flight_info("AMS", "BCN")  # ~1240 km -> €250
    disruption = FlightDisruption(
        flight=flight,
        disruption_type=DisruptionType.CANCELLATION,
        cancellation_notice_days=2,
    )
    result = evaluate_eu261(disruption)
    assert result.eligible is True
    assert result.compensation_amount == 250.0


# ── Denied Boarding Tests ─────────────────────────────────────────────────

def test_involuntary_denied_boarding(base_flight_info):
    """Involuntary denied boarding triggers immediate Art. 7 compensation."""
    flight = base_flight_info("FRA", "JFK")  # Long haul -> €600
    disruption = FlightDisruption(
        flight=flight,
        disruption_type=DisruptionType.DENIED_BOARDING,
        volunteered_seat=False,
    )
    result = evaluate_eu261(disruption)
    assert result.eligible is True
    assert result.compensation_amount == 600.0
    assert any("Article 4(3)" in r for r in result.applicable_rules)


def test_voluntary_denied_boarding(base_flight_info):
    """Voluntary surrender does not qualify for statutory cash compensation."""
    flight = base_flight_info("FRA", "JFK")
    disruption = FlightDisruption(
        flight=flight,
        disruption_type=DisruptionType.DENIED_BOARDING,
        volunteered_seat=True,
    )
    result = evaluate_eu261(disruption)
    assert result.eligible is False
    assert result.compensation_amount is None
    assert any("Article 4(1)" in r for r in result.applicable_rules)


# ── Scope Tests (Article 3) ───────────────────────────────────────────────

def test_scope_departure_from_eu_any_carrier(base_flight_info):
    """Non-EU airline departing EU is covered under Art. 3(1)(a)."""
    flight = base_flight_info("CDG", "JFK", airline="UA")  # United departing Paris
    disruption = FlightDisruption(
        flight=flight,
        disruption_type=DisruptionType.DELAY,
        arrival_delay_minutes=250,
        is_eu_carrier=False,
    )
    result = evaluate_eu261(disruption)
    assert result.eligible is True
    assert "Article 3(1)(a)" in result.reasoning


def test_scope_inbound_to_eu_non_eu_carrier_excluded(base_flight_info):
    """Non-EU airline departing non-EU arriving EU is NOT covered (Art. 3(1)(b))."""
    flight = base_flight_info("JFK", "CDG", airline="UA")  # United departing NY
    disruption = FlightDisruption(
        flight=flight,
        disruption_type=DisruptionType.DELAY,
        arrival_delay_minutes=300,
        is_eu_carrier=False,
    )
    result = evaluate_eu261(disruption)
    assert result.eligible is False
    assert "third-country carriers" in result.reasoning.lower() or "not apply" in result.reasoning.lower()


def test_scope_inbound_to_eu_community_carrier_included(base_flight_info):
    """EU airline departing non-EU arriving EU is covered (Art. 3(1)(b))."""
    flight = base_flight_info("JFK", "CDG", airline="AF")  # Air France departing NY
    disruption = FlightDisruption(
        flight=flight,
        disruption_type=DisruptionType.DELAY,
        arrival_delay_minutes=300,
        is_eu_carrier=True,
    )
    result = evaluate_eu261(disruption)
    assert result.eligible is True
    assert result.compensation_amount == 600.0
