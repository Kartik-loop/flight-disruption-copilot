"""Assess US refunds and oversales compensation using facts, never guessed fares.

Refunds are separate from compensation so the agent can request the correct remedy.
Sources checked for phase 4:
https://www.ecfr.gov/current/title-14/chapter-II/subchapter-A/part-250/section-250.5
https://www.transportation.gov/individuals/aviation-consumer-protection/bumping-oversales
https://www.transportation.gov/individuals/aviation-consumer-protection/refunds
"""

from datetime import date

from copilot.rules.airports import is_us_airport
from copilot.rules.checks import check_airports, unresolved
from copilot.schemas.flight import CompensationResult, DisruptionType, FlightDisruption, Region

DOT_DBC_CAP_200_PCT = 1075.0
DOT_DBC_CAP_400_PCT = 2150.0
DOT_SIGNIFICANT_DELAY_DOMESTIC_MINS = 180
DOT_SIGNIFICANT_DELAY_INTERNATIONAL_MINS = 360


def check_dot_scope(disruption: FlightDisruption) -> tuple[bool, bool, str]:
    """Distinguish broad refund coverage from US-departure-only oversales coverage."""
    dep, arr = disruption.flight.departure_airport, disruption.flight.arrival_airport
    domestic = is_us_airport(dep) and is_us_airport(arr)
    return is_us_airport(dep) or is_us_airport(arr), domestic, f"Flight {dep} to {arr}."


def evaluate_dot_denied_boarding(
    disruption: FlightDisruption,
    is_domestic: bool,
    scope_text: str,
) -> CompensationResult:
    """Require oversales facts and the offered schedule before calculating a fare multiplier."""
    if not is_us_airport(disruption.flight.departure_airport):
        return CompensationResult(
            eligible=False,
            regulation=Region.US,
            reasoning="Part 250 excludes departures outside the US.",
            applicable_rules=["14 CFR § 250.2"],
        )
    if disruption.volunteered_seat is True:
        return CompensationResult(
            eligible=False,
            regulation=Region.US,
            reasoning="Voluntary surrender is governed by the negotiated offer, not statutory DBC.",
            applicable_rules=["14 CFR § 250.2b (Voluntary Bump)"],
        )
    questions = []
    for field, question in [
        ("volunteered_seat", "Did you voluntarily give up your seat?"),
        ("denied_due_to_overbooking", "Was boarding denied because the flight was oversold?"),
        (
            "met_checkin_requirements",
            "Did you meet check-in deadlines with valid travel documents?",
        ),
        ("was_rerouted", "Did the airline offer alternate transportation?"),
    ]:
        if getattr(disruption, field) is None:
            questions.append(question)
    if questions:
        return unresolved(Region.US, "More oversales facts are needed.", questions)
    if not disruption.denied_due_to_overbooking or not disruption.met_checkin_requirements:
        return unresolved(
            Region.US,
            "The simplified oversales conditions are not established; this case needs review.",
        )
    # LEARN: The rule uses the alternative's planned arrival, not its eventual
    # actual delay. An unknown time does not mean a 99-hour delay or no alternative.
    delay = disruption.rerouting_arrival_delay_minutes
    if disruption.was_rerouted and delay is None:
        return unresolved(
            Region.US,
            "The alternative's scheduled arrival is missing.",
            ["How many minutes later was the alternative scheduled to arrive?"],
        )
    section = "a" if is_domestic else "b"
    if disruption.was_rerouted and delay <= 60:
        return CompensationResult(
            eligible=False,
            regulation=Region.US,
            compensation_amount=0,
            compensation_currency="USD",
            reasoning="Alternate arrival is within one hour.",
            applicable_rules=[f"14 CFR § 250.5({section})(1)"],
        )
    if disruption.one_way_fare_usd is None:
        return unresolved(
            Region.US,
            "An actual fare is required; a sample fare is not a payout.",
            ["What was the one-way fare in USD (or applicable zero-fare value)?"],
        )
    # NOTE: The CFR uses LESS THAN two/four hours. Exactly at the boundary
    # belongs to the higher tier, unlike the previous implementation's <= check.
    lower_tier = disruption.was_rerouted and delay < (120 if is_domestic else 240)
    multiplier, tier = (2, 2) if lower_tier else (4, 3)
    if disruption.flight.flight_date < date(2025, 1, 22):
        return unresolved(
            Region.US,
            "This learning engine uses caps effective January 22, 2025; "
            "historical caps need review.",
        )
    cap = DOT_DBC_CAP_200_PCT if lower_tier else DOT_DBC_CAP_400_PCT
    amount = round(min(multiplier * disruption.one_way_fare_usd, cap), 2)
    return CompensationResult(
        eligible=True,
        regulation=Region.US,
        compensation_amount=amount,
        compensation_currency="USD",
        reasoning=f"{scope_text} {multiplier * 100}% of the one-way fare, capped at "
        f"${cap:,.0f}, gives ${amount:,.2f}. Payment is by CASH or CHECK; vouchers "
        "are optional. Aircraft-size and other § 250.6 exceptions still need checking.",
        applicable_rules=[f"14 CFR § 250.5({section})({tier})", "14 CFR § 250.8"],
    )


def evaluate_dot(disruption: FlightDisruption) -> CompensationResult:
    """Represent refund conditions independently of the absence of fixed delay compensation."""
    if pending := check_airports(disruption, Region.US):
        return pending
    in_scope, domestic, scope_text = check_dot_scope(disruption)
    if not in_scope:
        return CompensationResult(eligible=False, regulation=Region.US, reasoning=scope_text)
    if disruption.disruption_type == DisruptionType.DENIED_BOARDING:
        return evaluate_dot_denied_boarding(disruption, domestic, scope_text)
    threshold = (
        DOT_SIGNIFICANT_DELAY_DOMESTIC_MINS
        if domestic
        else (DOT_SIGNIFICANT_DELAY_INTERNATIONAL_MINS)
    )
    cancellation = disruption.disruption_type == DisruptionType.CANCELLATION
    delay = disruption.arrival_delay_minutes
    if not cancellation and delay is None:
        return CompensationResult(
            eligible=False,
            regulation=Region.US,
            reasoning="NO STATUTORY DELAY COMPENSATION. Supply delay duration for refund review.",
            missing_information=["What was the arrival delay in minutes?"],
        )
    significant = cancellation or delay >= threshold
    questions = []
    if significant and disruption.declined_alternative_travel is None:
        questions.append("Did you decline travel and vouchers/credits after the disruption?")
    # LEARN: A refund returns unused ticket value; compensation is a separate
    # payment. A passenger can lack delay compensation and still have refund rights.
    explanation = (
        "REFUND assessment under 14 CFR Part 260: a cancellation or significant delay "
        f"({threshold // 60}+ hours) can trigger a refund of unused travel if the passenger "
        "declines travel and vouchers/credits. Refunds are generally due within 7 business "
        "days for credit-card payments or 20 calendar days for other payments."
        if significant
        else f"Arrival delay was less than {threshold // 60} hours. This does not qualify "
        "for the time-based refund rule; other significant schedule changes are not evaluated."
    )
    return CompensationResult(
        eligible=False,
        regulation=Region.US,
        refund_eligible=disruption.declined_alternative_travel if significant else None,
        compensation_currency="USD",
        missing_information=questions,
        reasoning=f"{scope_text} NO STATUTORY DELAY COMPENSATION or fixed cancellation award. "
        + explanation,
        applicable_rules=["14 CFR Part 260 (Refunds)", "14 CFR § 260.6"],
    )
