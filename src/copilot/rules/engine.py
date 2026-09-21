"""
copilot.rules.engine — Unified rules engine router.

WHAT: Routes a flight disruption claim to the appropriate legal framework
      (EU261, US DOT, or both) and returns a unified CompensationResult.
WHY:  Passengers often do not know which regulatory regime protects them.
      A flight from Paris to Chicago on American Airlines is governed by
      EU261 (departing EU), whereas Chicago to Paris on American is not (departing
      non-EU on a non-EU airline). The router inspects airport geography and
      airline nationality to automatically apply the most protective rules.
HOW:  1. Geographically analyzes departure and arrival airports.
      2. Checks EU261 eligibility (which generally provides superior cash remedies).
      3. Checks US DOT eligibility (for denied boarding or refund rights).
      4. Synthesizes an auditable, deterministic determination.

LEARN: The router pattern separates "what rules exist" from "which rules apply".
Each individual rule module (eu261.py, dot.py) only knows its own law.
The router provides the orchestrating logic that maps real-world flight
geography to the appropriate statute.
"""

from __future__ import annotations

from typing import Optional

from copilot.rules.airports import is_eu_airport, is_us_airport
from copilot.rules.dot import evaluate_dot
from copilot.rules.eu261 import evaluate_eu261
from copilot.schemas.flight import (
    CompensationResult,
    FlightDisruption,
    Region,
)


def determine_applicable_region(disruption: FlightDisruption) -> Region:
    """
    Determine the primary applicable regulatory jurisdiction for a flight.

    Hierarchy:
      1. If the flight falls within EU261 scope, EU takes precedence because
         EU261 provides statutory cash compensation (up to €600) for delays
         and cancellations, whereas US law does not.
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
                f"Flight from {dep} to {arr} falls outside both European Regulation (EC) No 261/2004 "
                f"and United States Department of Transportation jurisdiction. "
                f"Neither departure nor arrival connects to an EU or US airport. "
                f"International carriage may be governed by the Montreal Convention 1999 "
                f"or local civil aviation authority rules."
            ),
            applicable_rules=["Montreal Convention 1999 (General Aviation)"],
            extraordinary_circumstances=None,
        )
