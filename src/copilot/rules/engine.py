"""
copilot.rules.engine — Unified rules engine router.

WHAT: Routes a flight disruption claim to the appropriate legal framework
      (EU261, US DOT, or both) and returns a unified CompensationResult.
WHY:  Passengers often do not know which regulatory regime protects them.
      A flight from Paris to Chicago on American Airlines is governed by
      EU261 (departing EU), whereas Chicago to Paris on American is not (departing
      non-EU on a non-EU airline). The router inspects airport geography and
      airline nationality to select candidate regimes without ranking currencies.
HOW:  1. Geographically analyzes departure and arrival airports.
      2. Checks EU261 eligibility (which generally provides superior cash remedies).
      3. Checks US DOT eligibility (for denied boarding or refund rights).
      4. Returns a primary result, or separate results via evaluate_all_regimes.

LEARN: The router pattern separates "what rules exist" from "which rules apply".
Each individual rule module (eu261.py, dot.py) only knows its own law.
The router provides the orchestrating logic that maps real-world flight
geography to the appropriate statute.
"""

from __future__ import annotations

from typing import Optional

from copilot.rules.airports import is_eu_airport, is_us_airport
from copilot.rules.checks import check_airports
from copilot.rules.dot import evaluate_dot
from copilot.rules.eu261 import evaluate_eu261
from copilot.schemas.flight import (
    CompensationResult,
    FlightDisruption,
    Region,
)


def determine_applicable_region(disruption: FlightDisruption) -> Region:
    """
    Select the primary candidate jurisdiction; evaluators verify scope and missing facts.

    Hierarchy:
      1. Evaluate EU261 first for departures or potential covered arrivals.
         Unknown inbound carrier nationality produces a question, not coverage.
      2. If not EU-eligible but involves the US (domestic or US departure),
         US DOT applies.
      3. Otherwise, Region.OTHER.
    """
    dep = disruption.flight.departure_airport.upper()
    arr = disruption.flight.arrival_airport.upper()
    is_eu_carrier = disruption.is_eu_carrier

    dep_eu = is_eu_airport(dep)
    arr_eu = is_eu_airport(arr)
    dep_us = is_us_airport(dep)
    arr_us = is_us_airport(arr)

    # EU261 scope check:
    # 1. Any flight departing from EU airport (Art. 3(1)(a))
    # 2. Inbound flight to EU on an EU carrier (Art. 3(1)(b))
    if dep_eu or (arr_eu and (is_eu_carrier is not False)):
        return Region.EU

    # US DOT scope check:
    if dep_us or arr_us:
        return Region.US

    return Region.OTHER


def evaluate_disruption_rules(
    disruption: FlightDisruption, preferred_region: Optional[Region] = None
) -> CompensationResult:
    """
    Evaluate a flight disruption against applicable consumer protection regulations.

    Args:
      disruption: Structured facts about the disrupted flight.
      preferred_region: Optional manual override (Region.EU or Region.US).
                        If omitted, the engine auto-detects jurisdiction.

    Returns:
      CompensationResult with eligibility, payout amount, legal reasoning,
      and statutory citations.
    """
    region = preferred_region or determine_applicable_region(disruption)
    if pending := check_airports(disruption, region):
        return pending

    if region == Region.EU:
        return evaluate_eu261(disruption)
    elif region == Region.US:
        return evaluate_dot(disruption)
    else:
        dep = disruption.flight.departure_airport
        arr = disruption.flight.arrival_airport
        return CompensationResult(
            eligible=False,
            regulation=Region.OTHER,
            compensation_amount=None,
            compensation_currency=None,
            reasoning=(
                f"Flight from {dep} to {arr} is outside the implemented EU261 "
                f"and United States Department of Transportation jurisdiction. "
                f"No implemented regime covers the supplied route and carrier facts. "
                f"UK261 and other local regimes are not implemented. "
                f"International carriage may be governed by the Montreal Convention 1999 "
                f"or local civil aviation authority rules."
            ),
            applicable_rules=["Montreal Convention 1999 (General Aviation)"],
            extraordinary_circumstances=None,
        )


def evaluate_all_regimes(disruption: FlightDisruption) -> list[CompensationResult]:
    """Preserve separate EU and US remedies instead of losing one in the primary-region router.

    LEARN: Refunds and cash awards answer different questions and cannot be added
    together. Returning separate results lets the agent explain both without
    inventing a currency conversion or promising double recovery.
    """
    primary = evaluate_disruption_rules(disruption)
    results = [primary]
    if primary.regulation != Region.US and (
        is_us_airport(disruption.flight.departure_airport)
        or is_us_airport(disruption.flight.arrival_airport)
    ):
        results.append(evaluate_dot(disruption))
    return results
