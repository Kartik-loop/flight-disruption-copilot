"""Protect the agent boundary from definitive awards based on missing or contradictory facts.

These regressions cover the gaps found before phase 4, including separate refund
scope and compensation arithmetic at the exact DOT tier boundaries.
"""

from datetime import date

import pytest

from copilot.rules.dot import evaluate_dot
from copilot.rules.engine import evaluate_all_regimes, evaluate_disruption_rules
from copilot.rules.eu261 import classify_extraordinary_circumstances, evaluate_eu261
from copilot.schemas.flight import FlightDisruption, FlightInfo, Region


def disruption(dep="FRA", arr="CDG", kind="delay", **facts):
    """Keep route construction separate from the facts each regression deliberately omits."""
    return FlightDisruption(
        flight=FlightInfo(
            airline="LH", departure_airport=dep, arrival_airport=arr, flight_date=date(2025, 8, 1)
        ),
        disruption_type=kind,
        **facts,
    )


@pytest.mark.parametrize(
    "reason,expected",
    [
        ("Software issue", False),
        ("Departure delayed by severe weather", True),
        ("No bad weather", None),
        ("Technical problem and severe weather", None),
        ("Unexplained event", None),
    ],
)
def test_reason_boundaries_negation_and_mixed_causes(reason, expected):
    """Words inside other words, negation, and mixed causes must not fabricate an exemption."""
    assert classify_extraordinary_circumstances(reason)[0] is expected


@pytest.mark.parametrize(
    "case",
    [
        disruption("JFK", "CDG", arrival_delay_minutes=300, airline_reason="Technical fault"),
        disruption(kind="cancellation", airline_reason="Technical fault"),
        disruption(kind="denied_boarding"),
        disruption(arr="ZZZ", arrival_delay_minutes=300),
    ],
)
def test_unknown_inputs_are_not_awards(case):
    """Unknown nationality, notice, boarding facts, or geography must remain unresolved."""
    result = evaluate_disruption_rules(case)
    assert result.eligible is None
    assert result.compensation_amount is None
    assert result.missing_information or result.review_required


def test_foreign_departure_cannot_receive_us_bumping_award():
    """Inbound refund scope must not accidentally extend US oversales compensation abroad."""
    result = evaluate_dot(disruption("SIN", "JFK", "denied_boarding"))
    assert result.eligible is False
    assert result.compensation_amount is None


@pytest.mark.parametrize(
    "domestic,delay,amount",
    [
        (True, 60, 0),
        (True, 61, 500),
        (True, 119, 500),
        (True, 120, 1000),
        (False, 239, 500),
        (False, 240, 1000),
    ],
)
def test_dot_exact_planned_arrival_boundaries(domestic, delay, amount):
    """The CFR's strict lower-tier limit must use planned, not actual, alternate arrival."""
    result = evaluate_dot(
        disruption(
            "JFK",
            "LAX" if domestic else "SIN",
            "denied_boarding",
            volunteered_seat=False,
            was_rerouted=True,
            met_checkin_requirements=True,
            denied_due_to_overbooking=True,
            one_way_fare_usd=250,
            rerouting_arrival_delay_minutes=delay,
            arrival_delay_minutes=900,
        )
    )
    assert result.compensation_amount == amount


def test_missing_fare_and_alternate_delay_are_questions():
    """Omitted prices and offered schedules cannot become invented dollar estimates."""
    case = disruption(
        "JFK",
        "LAX",
        "denied_boarding",
        volunteered_seat=False,
        was_rerouted=True,
        met_checkin_requirements=True,
        denied_due_to_overbooking=True,
    )
    assert evaluate_dot(case).eligible is None
    case.rerouting_arrival_delay_minutes = 150
    result = evaluate_dot(case)
    assert result.eligible is None
    assert "fare" in result.missing_information[0]


@pytest.mark.parametrize("declined,expected", [(None, None), (True, True), (False, False)])
def test_refund_is_separate_and_conditional(declined, expected):
    """Cancellation alone establishes neither cash compensation nor an unconditional refund."""
    result = evaluate_dot(
        disruption("JFK", "LAX", "cancellation", declined_alternative_travel=declined)
    )
    assert result.eligible is False
    assert result.refund_eligible is expected
    assert bool(result.missing_information) is (declined is None)


def test_eu_and_us_results_both_survive():
    """A transatlantic case must preserve both the EU award and separate US refund assessment."""
    results = evaluate_all_regimes(
        disruption(
            "CDG",
            "JFK",
            "delay",
            arrival_delay_minutes=400,
            airline_reason="Technical fault",
            declined_alternative_travel=False,
        )
    )
    assert [result.regulation for result in results] == [Region.EU, Region.US]
    assert results[0].compensation_amount == 600
    assert results[1].eligible is False
    assert results[1].refund_eligible is False


@pytest.mark.parametrize(
    "notice,advance,planned,eligible",
    [
        (7, 120, 239, False),
        (7, 120, 240, True),
        (6, 60, 119, False),
        (6, 60, 120, True),
    ],
)
def test_cancellation_rerouting_exceptions(notice, advance, planned, eligible):
    """Notice-window exceptions use the offered schedule and strict arrival limits."""
    result = evaluate_eu261(
        disruption(
            kind="cancellation",
            cancellation_notice_days=notice,
            was_rerouted=True,
            rerouting_departure_advance_minutes=advance,
            rerouting_arrival_delay_minutes=planned,
            arrival_delay_minutes=400,
            airline_reason="Technical fault",
        )
    )
    assert result.eligible is eligible


def test_eu_rerouting_reduces_confirmed_amount():
    """An eligible rerouted cancellation can still qualify for the separate 50% reduction."""
    result = evaluate_eu261(
        disruption(
            kind="cancellation",
            cancellation_notice_days=2,
            was_rerouted=True,
            rerouting_departure_advance_minutes=180,
            rerouting_arrival_delay_minutes=100,
            arrival_delay_minutes=100,
            airline_reason="Technical fault",
        )
    )
    assert result.compensation_amount == 125


def test_weather_claim_requires_review_not_automatic_denial():
    """A reported cause cannot establish reasonable measures or causation by itself."""
    result = evaluate_eu261(disruption(arrival_delay_minutes=400, airline_reason="Severe weather"))
    assert result.eligible is None
    assert result.review_required
