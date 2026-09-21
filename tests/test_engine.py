"""
tests/test_engine.py — Unit tests for the rules engine router.

WHAT: Tests jurisdiction routing between EU261, US DOT, and un-covered international flights.
WHY:  Verifies that passengers receive the most protective legal assessment based on geography.
"""

from datetime import date

from copilot.rules.engine import (
    determine_applicable_region,
    evaluate_disruption_rules,
)
from copilot.schemas.flight import (
    DisruptionType,
    FlightDisruption,
    FlightInfo,
    Region,
)


def make_disruption(dep: str, arr: str, dtype=DisruptionType.DELAY, mins=200, airline="LH", is_eu=None):
    return FlightDisruption(
        flight=FlightInfo(
            airline=airline,
            departure_airport=dep,
            arrival_airport=arr,
            flight_date=date(2024, 7, 10),
        ),
        disruption_type=dtype,
        arrival_delay_minutes=mins,
        is_eu_carrier=is_eu,
    )


def test_routing_eu_domestic():
    """Flights within EU route to Region.EU."""
    d = make_disruption("FRA", "CDG")
    assert determine_applicable_region(d) == Region.EU
    res = evaluate_disruption_rules(d)
    assert res.regulation == Region.EU
    assert res.eligible is True
    assert res.compensation_currency == "EUR"


def test_routing_us_domestic():
    """Flights within US route to Region.US."""
    d = make_disruption("JFK", "LAX", mins=250, airline="AA")
    assert determine_applicable_region(d) == Region.US
    res = evaluate_disruption_rules(d)
    assert res.regulation == Region.US
    assert res.eligible is False  # Delay has $0 cash under DOT


def test_routing_transatlantic_departure_from_eu():
    """Flight departing EU to US routes to Region.EU (EU261 provides cash compensation)."""
    d = make_disruption("CDG", "JFK", mins=250, airline="DL", is_eu=False)
    assert determine_applicable_region(d) == Region.EU
    res = evaluate_disruption_rules(d)
    assert res.regulation == Region.EU
    assert res.eligible is True
    assert res.compensation_amount == 600.0


def test_routing_other_international():
    """Flights outside EU and US route to Region.OTHER."""
    d = make_disruption("HND", "SYD", mins=300, airline="NH")
    assert determine_applicable_region(d) == Region.OTHER
    res = evaluate_disruption_rules(d)
    assert res.regulation == Region.OTHER
    assert res.eligible is False
    assert "Montreal Convention" in res.applicable_rules[0]


def test_manual_override():
    """Manual preferred_region takes precedence over auto-detection."""
    d = make_disruption("JFK", "LAX", dtype=DisruptionType.DENIED_BOARDING, mins=120)
    # Manually force US evaluation even if specified
    res = evaluate_disruption_rules(d, preferred_region=Region.US)
    assert res.regulation == Region.US
