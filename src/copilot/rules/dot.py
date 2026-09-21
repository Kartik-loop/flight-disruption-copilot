"""
copilot.rules.dot — Deterministic compensation and refund engine for US DOT rules.

WHAT: Encodes federal aviation regulations under Title 14 of the Code of Federal Regulations
      (14 CFR Part 250 for Denied Boarding and 14 CFR Part 260 for Refunds).
WHY:  Unlike the European Union, the United States has NO statutory fixed cash compensation
      for flight delays alone. Conflating US rules with EU261 is the #1 mistake in air
      travel assistance tools. US law strictly governs:
        1. Involuntary Denied Boarding Compensation (14 CFR Part 250) based on one-way fare
           multipliers and federal statutory caps.
        2. Automatic Refunds for Cancellations and Significant Delays (14 CFR Part 260,
           April 2024 Final Rule 89 FR 32760).
HOW:  Deterministic Python evaluation of disruption facts against codified CFR provisions.

LEGAL AUTHORITIES CITED:
  - 14 CFR Part 250 — Oversales and Involuntary Denied Boarding Compensation
    https://www.ecfr.gov/current/title-14/chapter-II/subchapter-A/part-250
    Updated statutory limits: 89 FR 84816 (effective January 22, 2025), adjusting DBC caps
    to $1,075 (200%) and $2,150 (400%).
  - 14 CFR Part 260 — Refunds for Airline Fare and Ancillary Service Fees
    https://www.ecfr.gov/current/title-14/chapter-II/subchapter-A/part-260
    Department of Transportation Final Rule (89 FR 32760, April 2024): Uniform definition
    of "significant delay" (3+ hours domestic, 6+ hours international) entitling passengers
    who decline rerouting to a full automatic refund.
  - Official US DOT Guidance on Flight Delays:
    "In the United States, airlines are not required to compensate passengers whose flights
     are delayed or canceled. As a general rule, there are no federal requirements for airlines
     to provide passengers with money or other compensation when their flights are delayed."
"""

from __future__ import annotations

from typing import Optional, Tuple

from copilot.rules.airports import is_us_airport
from copilot.schemas.flight import (
    CompensationResult,
    DisruptionType,
    FlightDisruption,
    Region,
)


# ── US DOT Statutory Constants (14 CFR Part 250) ──────────────────────────
# LEARN: Caps were adjusted for inflation by the DOT in October 2024 (89 FR 84816)
# effective January 22, 2025. Previous caps were $775 and $1,550.
DOT_DBC_CAP_200_PCT = 1075.0  # 200% of one-way fare cap
DOT_DBC_CAP_400_PCT = 2150.0  # 400% of one-way fare cap

# Benchmark estimate for domestic one-way fare when user hasn't provided exact ticket price
# Used only to calculate estimated dollar amounts for display
ESTIMATED_ONE_WAY_FARE_USD = 250.0

# 14 CFR Part 260 Significant Delay Thresholds (hours / minutes)
DOT_SIGNIFICANT_DELAY_DOMESTIC_MINS = 180       # 3 hours
DOT_SIGNIFICANT_DELAY_INTERNATIONAL_MINS = 360  # 6 hours


def check_dot_scope(disruption: FlightDisruption) -> Tuple[bool, bool, str]:
    """
    Determine whether a flight is subject to US DOT passenger regulations.

    Returns:
      (in_scope, is_domestic, reason_text)

    Scope rules:
      - Domestic: Both departure and arrival in the US (14 CFR § 250.2).
      - International: Nonstop flights originating in the US (14 CFR § 250.2).
        Note: Flights to the US operated by foreign carriers are not covered by Part 250 DBC,
        though Part 260 refund rules apply to all tickets sold for US travel.
    """
    dep = disruption.flight.departure_airport.upper()
    arr = disruption.flight.arrival_airport.upper()

    dep_is_us = is_us_airport(dep)
    arr_is_us = is_us_airport(arr)

    if dep_is_us and arr_is_us:
        return (
            True,
            True,
            f"US Domestic flight ({dep} to {arr}). Fully subject to 14 CFR Part 250 (oversales) "
            f"and 14 CFR Part 260 (refunds).",
        )

    if dep_is_us and not arr_is_us:
        return (
            True,
            False,
            f"International flight originating in the US ({dep} to {arr}). Subject to US DOT "
            f"regulations under 14 CFR Part 250 and Part 260.",
        )

    if not dep_is_us and arr_is_us:
        # Inbound to US
        return (
            True,
            False,
            f"Inbound flight to the US ({dep} to {arr}). 14 CFR Part 260 refund rules apply to tickets "
            f"purchased for US travel, but Part 250 denied boarding compensation only applies to flights "
            f"originating at a point within the United States.",
        )

    return (
        False,
        False,
        f"Neither departure ({dep}) nor arrival ({arr}) is located in the United States. "
        f"US Department of Transportation rules do not apply.",
    )


# ── Involuntary Denied Boarding Evaluation (14 CFR Part 250) ───────────────

def evaluate_dot_denied_boarding(
    disruption: FlightDisruption, is_domestic: bool, scope_text: str
) -> CompensationResult:
    """
    Evaluate Involuntary Denied Boarding Compensation under 14 CFR § 250.5.

    Rules:
      - Voluntary surrender (§ 250.2b): No statutory DBC; negotiated compensation only.
      - Involuntary bump domestic:
        * Alternate arrives <= 1 hr after scheduled arrival: 0% ($0 compensation, § 250.5(a)(1)).
        * Alternate arrives 1–2 hrs after scheduled arrival: 200% one-way fare, max $1,075 (§ 250.5(a)(2)).
        * Alternate arrives > 2 hrs late (or no alternate): 400% one-way fare, max $2,150 (§ 250.5(a)(3)).
      - Involuntary bump international (departing US):
        * Alternate arrives <= 1 hr late: 0% ($0).
        * Alternate arrives 1–4 hrs late: 200% one-way fare, max $1,075 (§ 250.5(b)(2)).
        * Alternate arrives > 4 hrs late (or no alternate): 400% one-way fare, max $2,150 (§ 250.5(b)(3)).

    LEARN: Under 14 CFR § 250.8, the carrier must pay denied boarding compensation in
    CASH or immediately negotiable check on the day the bump occurs. The passenger is NOT
    obligated to accept travel vouchers or airline miles.
    """
    # Voluntary surrender
    if disruption.volunteered_seat is True:
        return CompensationResult(
            eligible=False,
            regulation=Region.US,
            compensation_amount=None,
            compensation_currency="USD",
            reasoning=(
                f"{scope_text}\n\n"
                f"Under 14 CFR § 250.2b, passengers who voluntarily surrender their seat are NOT entitled "
                f"to statutory denied boarding compensation. Compensation is strictly determined by the "
                f"negotiated offer agreed upon between the passenger and the airline at the gate."
            ),
            applicable_rules=["14 CFR § 250.2b (Voluntary Bump)"],
        )

    delay_mins = disruption.arrival_delay_minutes

    # If delay duration of alternate flight is unknown, assume long delay / no alternate
    if delay_mins is None:
        delay_hours = 99.0
    else:
        delay_hours = delay_mins / 60.0

    # Domestic tier thresholds
    if is_domestic:
        if delay_hours <= 1.0:
            return CompensationResult(
                eligible=False,
                regulation=Region.US,
                compensation_amount=0.0,
                compensation_currency="USD",
                reasoning=(
                    f"{scope_text}\n\n"
                    f"Under 14 CFR § 250.5(a)(1), if the airline arranges alternate transportation that arrives "
                    f"within 1 hour of the original scheduled arrival time, no denied boarding compensation is required."
                ),
                applicable_rules=["14 CFR § 250.5(a)(1)", "14 CFR § 250.6(d)"],
            )
        elif delay_hours <= 2.0:
            # 200% tier
            est_amount = min(2.0 * ESTIMATED_ONE_WAY_FARE_USD, DOT_DBC_CAP_200_PCT)
            return CompensationResult(
                eligible=True,
                regulation=Region.US,
                compensation_amount=est_amount,
                compensation_currency="USD",
                reasoning=(
                    f"{scope_text}\n\n"
                    f"ELIGIBLE FOR INVOLUNTARY DENIED BOARDING COMPENSATION (14 CFR § 250.5(a)(2)):\n"
                    f"Because alternate transportation arrives between 1 and 2 hours after your scheduled arrival, "
                    f"the airline owes you 200% of your one-way fare, capped at a statutory maximum of ${DOT_DBC_CAP_200_PCT:,.0f}.\n"
                    f"• Estimated payout based on ${ESTIMATED_ONE_WAY_FARE_USD:.0f} fare: ${est_amount:.0f}.\n"
                    f"• Under 14 CFR § 250.8, you have the legal right to demand payment by CASH or CHECK at the airport, "
                    f"not travel vouchers or credits."
                ),
                applicable_rules=["14 CFR § 250.5(a)(2)", "14 CFR § 250.8 (Payment method)"],
            )
        else:
            # 400% tier
            est_amount = min(4.0 * ESTIMATED_ONE_WAY_FARE_USD, DOT_DBC_CAP_400_PCT)
            return CompensationResult(
                eligible=True,
                regulation=Region.US,
                compensation_amount=est_amount,
                compensation_currency="USD",
                reasoning=(
                    f"{scope_text}\n\n"
                    f"ELIGIBLE FOR INVOLUNTARY DENIED BOARDING COMPENSATION (14 CFR § 250.5(a)(3)):\n"
                    f"Because alternate transportation arrives more than 2 hours after scheduled arrival (or was not arranged), "
                    f"the airline owes you 400% of your one-way fare, capped at a statutory maximum of ${DOT_DBC_CAP_400_PCT:,.0f}.\n"
                    f"• Estimated payout based on ${ESTIMATED_ONE_WAY_FARE_USD:.0f} fare: ${est_amount:.0f}.\n"
                    f"• Under 14 CFR § 250.8, you have the legal right to demand payment by CASH or CHECK at the airport."
                ),
                applicable_rules=["14 CFR § 250.5(a)(3)", "14 CFR § 250.8 (Payment method)"],
            )

    # International tier thresholds (originating in US)
    else:
        if delay_hours <= 1.0:
            return CompensationResult(
                eligible=False,
                regulation=Region.US,
                compensation_amount=0.0,
                compensation_currency="USD",
                reasoning=(
                    f"{scope_text}\n\n"
                    f"Under 14 CFR § 250.5(b)(1), no compensation is due if alternate transportation arrives "
                    f"within 1 hour of scheduled arrival."
                ),
                applicable_rules=["14 CFR § 250.5(b)(1)"],
            )
        elif delay_hours <= 4.0:
            est_amount = min(2.0 * ESTIMATED_ONE_WAY_FARE_USD, DOT_DBC_CAP_200_PCT)
            return CompensationResult(
                eligible=True,
                regulation=Region.US,
                compensation_amount=est_amount,
                compensation_currency="USD",
                reasoning=(
                    f"{scope_text}\n\n"
                    f"ELIGIBLE FOR INVOLUNTARY DENIED BOARDING COMPENSATION (14 CFR § 250.5(b)(2)):\n"
                    f"For international departures from the US where alternate transportation arrives between 1 and 4 hours late, "
                    f"the airline owes 200% of one-way fare (max ${DOT_DBC_CAP_200_PCT:,.0f}).\n"
                    f"• Payment must be made by CASH or CHECK under 14 CFR § 250.8."
                ),
                applicable_rules=["14 CFR § 250.5(b)(2)", "14 CFR § 250.8"],
            )
        else:
            est_amount = min(4.0 * ESTIMATED_ONE_WAY_FARE_USD, DOT_DBC_CAP_400_PCT)
            return CompensationResult(
                eligible=True,
                regulation=Region.US,
                compensation_amount=est_amount,
                compensation_currency="USD",
                reasoning=(
                    f"{scope_text}\n\n"
                    f"ELIGIBLE FOR INVOLUNTARY DENIED BOARDING COMPENSATION (14 CFR § 250.5(b)(3)):\n"
                    f"For international departures where alternate arrival delay exceeds 4 hours, the airline owes "
                    f"400% of one-way fare (statutory maximum ${DOT_DBC_CAP_400_PCT:,.0f}). Cash/check required."
                ),
                applicable_rules=["14 CFR § 250.5(b)(3)", "14 CFR § 250.8"],
            )


# ── Delay & Cancellation Evaluation (14 CFR Part 260) ──────────────────────

def evaluate_dot(disruption: FlightDisruption) -> CompensationResult:
    """
    Evaluate rights under US Department of Transportation aviation consumer protection rules.

    CRITICAL LEGAL REALITY CHECK:
      1. Delays: There is NO US federal regulation mandating cash compensation for delays.
         However, under the April 2024 DOT Final Rule (14 CFR Part 260), if a flight has a
         'significant delay' (3+ hours domestic, 6+ hours international) and the passenger
         chooses not to travel, the airline MUST provide a full prompt refund.
      2. Cancellations: Airlines must issue a full prompt refund if alternative travel
         is rejected. No fixed statutory compensation penalty exists under federal law.
      3. Denied Boarding: Governed by 14 CFR Part 250 (up to $2,150).
    """
    in_scope, is_domestic, scope_text = check_dot_scope(disruption)
    if not in_scope:
        return CompensationResult(
            eligible=False,
            regulation=Region.US,
            reasoning=scope_text,
            applicable_rules=[],
        )

    # ── CASE 1: DENIED BOARDING ───────────────────────────────────────────
    if disruption.disruption_type == DisruptionType.DENIED_BOARDING:
        return evaluate_dot_denied_boarding(disruption, is_domestic, scope_text)

    # ── CASE 2: CANCELLATION ──────────────────────────────────────────────
    if disruption.disruption_type == DisruptionType.CANCELLATION:
        # Under 14 CFR § 260.6, passengers have the absolute legal right to a full refund
        # to the original form of payment if they decline alternate transportation.
        return CompensationResult(
            eligible=False,  # NOTE: No statutory 'compensation' bonus exists in US law
            regulation=Region.US,
            compensation_amount=None,
            compensation_currency="USD",
            reasoning=(
                f"{scope_text}\n\n"
                f"US DOT REFUND ENTITLEMENT (14 CFR Part 260 — April 2024 Final Rule):\n"
                f"Under US federal law, airlines are NOT required to pay fixed statutory compensation "
                f"for cancellations. However, you have an absolute right to a FULL REFUND of your unused "
                f"ticket and ancillary fees (Wi-Fi, seat selection, baggage) if you reject alternative "
                f"transportation or rebooking.\n\n"
                f"• Refund method: Original form of payment (cash, credit card). Not airline vouchers.\n"
                f"• Timeline: Within 7 business days for credit cards, 20 calendar days for other payment methods "
                f"(14 CFR § 260.6)."
            ),
            applicable_rules=[
                "14 CFR Part 260 (Refunds for Airline Fare)",
                "14 CFR § 260.6 (Prompt Refund Requirements)",
                "DOT Final Rule 89 FR 32760",
            ],
        )

    # ── CASE 3: DELAY ─────────────────────────────────────────────────────
    if disruption.disruption_type == DisruptionType.DELAY:
        delay_mins = disruption.arrival_delay_minutes or 0
        threshold_mins = (
            DOT_SIGNIFICANT_DELAY_DOMESTIC_MINS
            if is_domestic
            else DOT_SIGNIFICANT_DELAY_INTERNATIONAL_MINS
        )
        threshold_hours = threshold_mins // 60

        is_significant = delay_mins >= threshold_mins

        if is_significant:
            return CompensationResult(
                eligible=False,
                regulation=Region.US,
                compensation_amount=None,
                compensation_currency="USD",
                reasoning=(
                    f"{scope_text}\n\n"
                    f"NO STATUTORY DELAY COMPENSATION UNDER US LAW:\n"
                    f"Unlike European Regulation EC 261/2004, United States federal law DOES NOT mandate "
                    f"fixed monetary compensation for delayed flights, regardless of how long the delay lasts.\n\n"
                    f"HOWEVER — REFUND RIGHT TRIGGERED (14 CFR § 260.2 & § 260.6):\n"
                    f"Your delay of {delay_mins} minutes meets the DOT threshold for a 'significant delay' "
                    f"({threshold_hours}+ hours for {'domestic' if is_domestic else 'international'} flights). "
                    f"If you choose NOT to travel, you are legally entitled to a 100% prompt refund of your unused "
                    f"ticket and ancillary fees to your original form of payment.\n\n"
                    f"• Note: If you completed your travel, airlines are not legally required to provide cash, "
                    f"though major US carriers have voluntary commitments on the DOT Dashboard for meal vouchers "
                    f"(3+ hr delay) or hotel accommodations (overnight delay) for controllable causes."
                ),
                applicable_rules=[
                    "14 CFR § 260.2 (Definition of Significant Delay)",
                    "14 CFR § 260.6 (Refund Eligibility)",
                    "14 CFR § 259.5 (Customer Service Commitments)",
                ],
            )
        else:
            return CompensationResult(
                eligible=False,
                regulation=Region.US,
                compensation_amount=None,
                compensation_currency="USD",
                reasoning=(
                    f"{scope_text}\n\n"
                    f"NO COMPENSATION: The flight was delayed {delay_mins} minutes. "
                    f"Under US law, airlines are not required to provide compensation for delays. "
                    f"Furthermore, because the delay was less than {threshold_hours} hours, it does not qualify "
                    f"as a 'significant delay' under 14 CFR § 260.2 that would mandate a right to a ticket refund."
                ),
                applicable_rules=["14 CFR § 260.2"],
            )

    return CompensationResult(
        eligible=False,
        regulation=Region.US,
        reasoning=f"Unsupported disruption type under US DOT rules: {disruption.disruption_type}",
        applicable_rules=[],
    )
