"""Shared uncertainty checks keep incomplete facts out of compensation arithmetic.

The engine needs more than a Boolean denial: a missing fact is a question, while
an unsupported situation needs review. Both must remain distinguishable from
an assessed lack of entitlement in the agent's final response.
"""

from copilot.rules.airports import get_airport
from copilot.schemas.flight import CompensationResult, FlightDisruption, Region


def unresolved(
    region: Region,
    reasoning: str,
    questions: list[str] | None = None,
) -> CompensationResult:
    """Make uncertainty explicit so a drafter cannot mistake it for an approved payout."""
    return CompensationResult(
        eligible=None,
        regulation=region,
        reasoning=reasoning,
        missing_information=questions or [],
        review_required=not bool(questions),
    )


def check_airports(disruption: FlightDisruption, region: Region) -> CompensationResult | None:
    """Stop when the small local airport table cannot support geography or distance claims."""
    codes = [disruption.flight.departure_airport, disruption.flight.arrival_airport]
    unknown = [code for code in codes if get_airport(code) is None]
    if unknown:
        return unresolved(
            region,
            f"Airport data unavailable for {', '.join(unknown)}. "
            "Verify the code and extend the airport table before assessment.",
        )
    return None
