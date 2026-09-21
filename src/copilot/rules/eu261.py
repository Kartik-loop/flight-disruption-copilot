"""
copilot.rules.eu261 — Deterministic compensation engine for Regulation (EC) No 261/2004.

WHAT: Encodes the statutory rules and CJEU jurisprudence of European flight passenger rights.
WHY:  Compensation entitlement under EU261 is governed by precise legal criteria:
      territorial scope (Art. 3), disruption categories (Arts. 4, 5, 6), distance bands
      (Art. 7(1)), reduction clauses (Art. 7(2)), and extraordinary circumstances (Art. 5(3)).
      An LLM must NEVER guess or hallucinate these values.
HOW:  Pure, deterministic Python functions evaluate a FlightDisruption object,
      calculate distance using great-circle route method (Art. 7(4)), and return
      an auditable CompensationResult citing specific articles and CJEU cases.

LEGAL AUTHORITIES CITED:
  - Regulation (EC) No 261/2004 of the European Parliament and of the Council
    https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=celex%3A32004R0261
  - Sturgeon v Condor Flugdienst GmbH (Joined Cases C-402/07 & C-432/07, 19 Nov 2009)
    Established equal treatment: arrival delay >= 3 hours at final destination qualifies
    for Art. 7 compensation as if cancelled.
  - Wallentin-Hermann v Alitalia (Case C-549/07, 22 Dec 2008)
    Two-pronged test for 'extraordinary circumstances' (Art. 5(3)): event must be
    not inherent in normal activity AND beyond actual control. Technical faults are NOT exempt.
  - Bossen v Brussels Airlines (Case C-559/16, 7 Sep 2017)
    Direct great-circle distance between departure and final destination, not route legs.
"""

from __future__ import annotations

import re
from typing import Optional, Tuple

from copilot.rules.airports import (
    calculate_flight_distance_km,
    is_eu_airport,
    is_intra_eu_flight,
)
from copilot.schemas.flight import (
    CompensationResult,
    DisruptionType,
    FlightDisruption,
    Region,
)


# ── EU261 Statutory Constants ─────────────────────────────────────────────

# Article 7(1) Distance thresholds (km)
DISTANCE_SHORT_KM = 1500.0
DISTANCE_LONG_KM = 3500.0

# Article 7(1) Base compensation amounts (EUR)
COMPENSATION_SHORT_EUR = 250.0  # Art. 7(1)(a): <= 1,500 km
COMPENSATION_MEDIUM_EUR = 400.0  # Art. 7(1)(b): 1,500-3,500 km OR intra-EU > 1,500 km
COMPENSATION_LONG_EUR = 600.0    # Art. 7(1)(c): > 3,500 km non-intra-EU

# Sturgeon ruling delay threshold (hours / minutes)
DELAY_THRESHOLD_HOURS = 3
DELAY_THRESHOLD_MINUTES = 180

# Article 7(2) 50% Reduction threshold for extra-EU long-haul flights (hours / minutes)
LONG_HAUL_REDUCTION_DELAY_MINUTES = 240  # 4 hours


# ── Extraordinary Circumstances Classification ────────────────────────────
# LEARN: Under Article 5(3) and CJEU Wallentin-Hermann (Case C-549/07), airlines
# are only exempt if the disruption was caused by 'extraordinary circumstances'
# that could not have been avoided even if all reasonable measures had been taken.
#
# Common airline practice: airlines frequently tell passengers "technical issues"
# or "crew sickness" is an extraordinary circumstance to avoid paying.
# In European law, this is FALSE:
#   - Technical failures are inherent in operating an aircraft (van der Lans, C-257/14)
#   - Airline's own staff strikes are NOT extraordinary (Airhelp v SAS, C-28/20)
#   - Crew shortages/sickness are operational risks inherent in airline management

EXEMPT_EXTRAORDINARY_PATTERNS = [
    r"weather",
    r"meteorological",
    r"fog",
    r"snow",
    r"storm",
    r"hurricane",
    r"volcan",
    r"ash",
    r"air traffic control",
    r"atc",
    r"bird strike",
    r"security",
    r"sabotage",
    r"closure of runway",
    r"airport closure",
    r"political instability",
    r"war",
    r"drone",
]

NON_EXEMPT_OPERATIONAL_PATTERNS = [
    r"technical",
    r"mechanical",
    r"aircraft maintenance",
    r"engine",
    r"part",
    r"sensor",
    r"crew sick",
    r"crew hour",
    r"crew timeout",
    r"crew short",
    r"staff short",
    r"pilot sick",
    r"internal strike",
    r"airline strike",
    r"cabin crew strike",
    r"operational reason",
]


def classify_extraordinary_circumstances(reason: Optional[str]) -> Tuple[Optional[bool], str]:
    """
    Evaluate whether the airline's stated reason qualifies as an 'extraordinary circumstance'.

    Returns:
      (is_extraordinary, explanation_note)
      - True: likely exempt under Art. 5(3) (weather, ATC, security, bird strike)
      - False: NOT exempt under CJEU case law (technical defect, internal strike, crew)
      - None: unclear or no reason provided
    """
    if not reason or not reason.strip():
        return None, "No disruption reason provided by airline."

    clean_reason = reason.strip().lower()

    # Check non-exempt patterns first (technical defects, staff shortages, internal strikes)
    for pattern in NON_EXEMPT_OPERATIONAL_PATTERNS:
        if re.search(pattern, clean_reason):
            return False, (
                f"The stated reason ('{reason}') appears to be an operational or technical issue. "
                f"Under CJEU Case C-549/07 (Wallentin-Hermann) and Case C-257/14 (van der Lans), "
                f"technical breakdowns and staffing shortages are inherent in the normal activity "
                f"of the air carrier and do NOT qualify as extraordinary circumstances."
            )

    # Check genuine extraordinary patterns (weather, ATC, security)
    for pattern in EXEMPT_EXTRAORDINARY_PATTERNS:
        if re.search(pattern, clean_reason):
            return True, (
                f"The stated reason ('{reason}') indicates an external event beyond the airline's control. "
                f"Under EU261 Article 5(3) and Recital 14, adverse meteorological conditions, "
                f"air traffic management directives, and third-party security events generally "
                f"constitute extraordinary circumstances exempting the carrier from compensation."
            )

    return None, f"Stated reason ('{reason}') requires further factual investigation."


# ── Scope Assessment (Article 3) ──────────────────────────────────────────

def check_eu261_scope(disruption: FlightDisruption) -> Tuple[bool, str]:
    """
    Determine whether a flight is within the territorial and legal scope of EU261.

    Article 3(1) Scope Conditions:
      (a) Departures from an EU/EEA/Swiss airport (any airline).
      (b) Departures from a third country arriving at an EU/EEA/Swiss airport,
          IF the operating carrier is an EU/EEA carrier.

    LEARN: A US carrier (e.g. United Airlines) flying Paris -> New York is COVERED
    by EU261 because it departs from the EU (Art. 3(1)(a)).
    However, the same carrier flying New York -> Paris is NOT covered because
    it departs outside the EU and United is not an EU carrier (Art. 3(1)(b)).
    """
    dep = disruption.flight.departure_airport.upper()
    arr = disruption.flight.arrival_airport.upper()
    is_eu_carrier = disruption.is_eu_carrier

    dep_in_eu = is_eu_airport(dep)
    arr_in_eu = is_eu_airport(arr)

    # Article 3(1)(a): Departing from an EU airport
    if dep_in_eu:
        return True, (
            f"Flight departs from {dep} (EU/EEA jurisdiction). Under Regulation (EC) No 261/2004 "
            f"Article 3(1)(a), the regulation applies to all flights departing from an airport "
            f"in an EU Member State regardless of the carrier's nationality."
        )

    # Article 3(1)(b): Departing from outside EU to EU airport on an EU carrier
    if arr_in_eu:
        if is_eu_carrier is True:
            return True, (
                f"Flight departs from outside EU ({dep}) to an EU airport ({arr}) and is operated "
                f"by a Community (EU) carrier. Covered under Article 3(1)(b)."
            )
        elif is_eu_carrier is False:
            return False, (
                f"Flight departs from outside the EU ({dep}) to {arr}, and is operated by a "
                f"non-EU carrier. Under Article 3(1)(b), EU261 does NOT apply to inbound flights "
                f"operated by third-country carriers."
            )
        else:
            # Carrier nationality unspecified; flag probable coverage if EU airport destination
            return True, (
                f"Flight arrives in the EU ({arr}) from a third country ({dep}). Under Article 3(1)(b), "
                f"EU261 applies if the operating airline is a Community (EU) carrier."
            )

    # Neither departure nor arrival in EU
    return False, (
        f"Neither departure ({dep}) nor arrival ({arr}) is in the EU/EEA. "
        f"EU Regulation 261/2004 does not apply."
    )


# ── Distance & Amount Calculation (Article 7) ─────────────────────────────

def calculate_eu261_compensation_amount(
    departure_iata: str, arrival_iata: str, delay_minutes: Optional[int] = None
) -> Tuple[float, str, list[str]]:
    """
    Calculate the exact statutory compensation amount under Article 7.

    Rules:
      - <= 1500 km: €250 (Art. 7(1)(a))
      - Intra-EU flights > 1500 km: €400 (Art. 7(1)(b)) [capped regardless of distance!]
      - Extra-EU flights 1500–3500 km: €400 (Art. 7(1)(b))
      - Extra-EU flights > 3500 km: €600 (Art. 7(1)(c))
        * Sub-rule (Art. 7(2)(c) & Sturgeon para 63): If the arrival delay for long-haul
          is between 3 and 4 hours (180–239 mins), compensation is reduced by 50% to €300.

    LEARN: The intra-EU exception in Article 7(1)(b) is frequently missed!
    A flight from Paris (CDG) to Réunion Island (RUN) is ~9,360 km. Even though
    it is over 3,500 km, Réunion is an EU Outermost Region (France).
    Because both ends are within the EU, Article 7(1)(b) caps compensation at €400,
    NOT €600.
    """
    distance_km = calculate_flight_distance_km(departure_iata, arrival_iata)
    intra_eu = is_intra_eu_flight(departure_iata, arrival_iata)

    rules = []

    # Band A: <= 1,500 km
    if distance_km <= DISTANCE_SHORT_KM:
        rules.append("Regulation (EC) No 261/2004 Art. 7(1)(a) (<= 1500 km)")
        return (
            COMPENSATION_SHORT_EUR,
            f"Flight distance is {distance_km:,.0f} km (<= 1,500 km). "
            f"Statutory compensation is €250 pursuant to Article 7(1)(a).",
            rules,
        )

    # Band B1: Intra-EU > 1,500 km
    if intra_eu:
        rules.append("Regulation (EC) No 261/2004 Art. 7(1)(b) (Intra-Community > 1500 km)")
        return (
            COMPENSATION_MEDIUM_EUR,
            f"Flight distance is {distance_km:,.0f} km between EU airports. "
            f"All intra-Community flights exceeding 1,500 km are capped at €400 pursuant to Article 7(1)(b).",
            rules,
        )

    # Band B2: Extra-EU 1,500–3,500 km
    if distance_km <= DISTANCE_LONG_KM:
        rules.append("Regulation (EC) No 261/2004 Art. 7(1)(b) (1500–3500 km)")
        return (
            COMPENSATION_MEDIUM_EUR,
            f"Flight distance is {distance_km:,.0f} km (between 1,500 km and 3,500 km). "
            f"Statutory compensation is €400 pursuant to Article 7(1)(b).",
            rules,
        )

    # Band C: Extra-EU > 3,500 km
    # Check 50% reduction clause for delays between 3h and 4h (Sturgeon para 63 & Art 7(2)(c))
    if delay_minutes is not None and DELAY_THRESHOLD_MINUTES <= delay_minutes < LONG_HAUL_REDUCTION_DELAY_MINUTES:
        rules.append("Regulation (EC) No 261/2004 Art. 7(1)(c) (> 3500 km)")
        rules.append("Regulation (EC) No 261/2004 Art. 7(2)(c) (50% reduction for delay < 4 hours)")
        return (
            300.0,
            f"Flight distance is {distance_km:,.0f} km (> 3,500 km, extra-Community). "
            f"Base compensation is €600 under Article 7(1)(c), but reduced by 50% to €300 "
            f"under Article 7(2)(c) because final arrival delay was under 4 hours ({delay_minutes} mins).",
            rules,
        )

    rules.append("Regulation (EC) No 261/2004 Art. 7(1)(c) (> 3500 km)")
    return (
        COMPENSATION_LONG_EUR,
        f"Flight distance is {distance_km:,.0f} km (> 3,500 km, extra-Community). "
        f"Statutory compensation is €600 pursuant to Article 7(1)(c).",
        rules,
    )


# ── Main EU261 Evaluation Engine ──────────────────────────────────────────

def evaluate_eu261(disruption: FlightDisruption) -> CompensationResult:
    """
    Evaluate passenger compensation eligibility under EU Regulation (EC) No 261/2004.

    Evaluates:
      1. Scope (Article 3)
      2. Disruption specifics:
         - DELAY: Sturgeon ruling (3+ hours at final destination)
         - CANCELLATION: Notice periods (<7 days, 7-14 days, >=14 days under Art. 5(1)(c))
         - DENIED BOARDING: Involuntary vs voluntary under Art. 4
      3. Extraordinary circumstances exemption (Art. 5(3))
      4. Statutory compensation amount calculation (Art. 7)
    """
    # 1. Scope check
    in_scope, scope_reason = check_eu261_scope(disruption)
    if not in_scope:
        return CompensationResult(
            eligible=False,
            regulation=Region.EU,
            compensation_amount=None,
            compensation_currency=None,
            reasoning=scope_reason,
            applicable_rules=["Regulation (EC) No 261/2004 Article 3"],
            extraordinary_circumstances=None,
        )

    # 2. Check extraordinary circumstances (applies to delay & cancellation)
    is_extraordinary, extra_note = classify_extraordinary_circumstances(disruption.airline_reason)
    if is_extraordinary is True and disruption.disruption_type in (
        DisruptionType.DELAY,
        DisruptionType.CANCELLATION,
    ):
        return CompensationResult(
            eligible=False,
            regulation=Region.EU,
            compensation_amount=None,
            compensation_currency=None,
            reasoning=(
                f"{scope_reason}\n\n"
                f"However, compensation is NOT due under Article 5(3) because the disruption was "
                f"caused by extraordinary circumstances: {extra_note}"
            ),
            applicable_rules=[
                "Regulation (EC) No 261/2004 Article 3",
                "Regulation (EC) No 261/2004 Article 5(3)",
            ],
            extraordinary_circumstances=True,
        )

    dep = disruption.flight.departure_airport
    arr = disruption.flight.arrival_airport

    # 3. Disruption type evaluation

    # ── CASE A: DELAY ─────────────────────────────────────────────────────
    if disruption.disruption_type == DisruptionType.DELAY:
        delay_mins = disruption.arrival_delay_minutes

        if delay_mins is None:
            return CompensationResult(
                eligible=False,
                regulation=Region.EU,
                reasoning=(
                    f"{scope_reason}\n\n"
                    f"To evaluate compensation for delay, the exact arrival delay at final destination "
                    f"is required. Under CJEU Sturgeon jurisprudence, delay must be 3 or more hours (180+ mins)."
                ),
                applicable_rules=["CJEU Joined Cases C-402/07 and C-432/07 (Sturgeon)"],
            )

        if delay_mins < DELAY_THRESHOLD_MINUTES:
            return CompensationResult(
                eligible=False,
                regulation=Region.EU,
                compensation_amount=None,
                compensation_currency=None,
                reasoning=(
                    f"{scope_reason}\n\n"
                    f"The flight arrived {delay_mins} minutes late. Under CJEU Sturgeon v Condor (C-402/07), "
                    f"passengers are only entitled to Article 7 compensation if the delay at final destination "
                    f"is 3 hours (180 minutes) or more. For delays of 2+ hours, airlines must offer right to care "
                    f"(meals/refreshments under Article 9), but no cash compensation is owed."
                ),
                applicable_rules=[
                    "Regulation (EC) No 261/2004 Article 6",
                    "CJEU Joined Cases C-402/07 and C-432/07 (Sturgeon v Condor)",
                ],
                extraordinary_circumstances=is_extraordinary,
            )

        # Delay >= 3 hours -> Entitled to Art 7 compensation!
        amount, dist_reason, rules = calculate_eu261_compensation_amount(dep, arr, delay_mins)
        rules.insert(0, "CJEU Joined Cases C-402/07 and C-432/07 (Sturgeon v Condor)")
        if is_extraordinary is False:
            rules.append("CJEU Case C-549/07 (Wallentin-Hermann: technical faults not exempt)")

        return CompensationResult(
            eligible=True,
            regulation=Region.EU,
            compensation_amount=amount,
            compensation_currency="EUR",
            reasoning=(
                f"{scope_reason}\n\n"
                f"ELIGIBLE FOR COMPENSATION: The flight arrived {delay_mins} minutes late (>= 3 hours). "
                f"Under the landmark CJEU Sturgeon v Condor ruling, passengers with 3+ hour arrival delays "
                f"have the right to Article 7 compensation.\n\n"
                f"{dist_reason}\n\n"
                f"{extra_note}"
            ),
            applicable_rules=rules,
            extraordinary_circumstances=is_extraordinary,
        )

    # ── CASE B: CANCELLATION ──────────────────────────────────────────────
    if disruption.disruption_type == DisruptionType.CANCELLATION:
        notice_days = disruption.cancellation_notice_days

        # Article 5(1)(c)(i): Informed at least 14 days prior
        if notice_days is not None and notice_days >= 14:
            return CompensationResult(
                eligible=False,
                regulation=Region.EU,
                compensation_amount=None,
                compensation_currency=None,
                reasoning=(
                    f"{scope_reason}\n\n"
                    f"The cancellation was announced {notice_days} days in advance. Under Article 5(1)(c)(i), "
                    f"no compensation is due if passengers are informed of the cancellation at least two weeks (14 days) "
                    f"before the scheduled departure. Note: You remain entitled to a full ticket refund or rerouting under Article 8."
                ),
                applicable_rules=["Regulation (EC) No 261/2004 Article 5(1)(c)(i)"],
                extraordinary_circumstances=is_extraordinary,
            )

        # Cancellation with short notice (< 14 days or notice unknown)
        amount, dist_reason, rules = calculate_eu261_compensation_amount(dep, arr)
        rules.insert(0, "Regulation (EC) No 261/2004 Article 5(1)(c)")
        rules.insert(1, "Regulation (EC) No 261/2004 Article 8 (Right to reimbursement or rerouting)")

        notice_text = (
            f"The flight was cancelled with {notice_days} days notice (less than 14 days)."
            if notice_days is not None
            else "The flight was cancelled with short notice."
        )

        return CompensationResult(
            eligible=True,
            regulation=Region.EU,
            compensation_amount=amount,
            compensation_currency="EUR",
            reasoning=(
                f"{scope_reason}\n\n"
                f"ELIGIBLE FOR COMPENSATION: {notice_text} Under Article 5(1)(c), cancellations informed "
                f"less than 14 days prior require statutory compensation unless the airline proved suitable rerouting "
                f"or extraordinary circumstances.\n\n"
                f"{dist_reason}\n\n"
                f"{extra_note}"
            ),
            applicable_rules=rules,
            extraordinary_circumstances=is_extraordinary,
        )

    # ── CASE C: DENIED BOARDING ───────────────────────────────────────────
    if disruption.disruption_type == DisruptionType.DENIED_BOARDING:
        # Article 4(1): Voluntary surrender
        if disruption.volunteered_seat is True:
            return CompensationResult(
                eligible=False,
                regulation=Region.EU,
                compensation_amount=None,
                compensation_currency=None,
                reasoning=(
                    f"{scope_reason}\n\n"
                    f"Under Article 4(1), passengers who voluntarily surrender their reservation do so in exchange "
                    f"for benefits agreed between the passenger and the airline, plus assistance under Article 8. "
                    f"Statutory Article 7 fixed compensation applies only to passengers denied boarding against their will (involuntarily)."
                ),
                applicable_rules=[
                    "Regulation (EC) No 261/2004 Article 4(1) (Voluntary surrender)",
                    "Regulation (EC) No 261/2004 Article 8",
                ],
                extraordinary_circumstances=None,
            )

        # Article 4(3): Involuntary denied boarding (e.g. overbooking)
        amount, dist_reason, rules = calculate_eu261_compensation_amount(dep, arr)
        rules.insert(0, "Regulation (EC) No 261/2004 Article 4(3) (Involuntary denied boarding)")

        return CompensationResult(
            eligible=True,
            regulation=Region.EU,
            compensation_amount=amount,
            compensation_currency="EUR",
            reasoning=(
                f"{scope_reason}\n\n"
                f"ELIGIBLE FOR COMPENSATION: Under Article 4(3), if boarding is denied to passengers against their will, "
                f"the operating air carrier must immediately compensate them in accordance with Article 7, "
                f"as well as provide rerouting/refund (Article 8) and care (Article 9).\n\n"
                f"{dist_reason}"
            ),
            applicable_rules=rules,
            extraordinary_circumstances=False,
        )

    # Fallback for unrecognized disruption types
    return CompensationResult(
        eligible=False,
        regulation=Region.EU,
        reasoning=f"Unsupported disruption type: {disruption.disruption_type}",
        applicable_rules=[],
    )
