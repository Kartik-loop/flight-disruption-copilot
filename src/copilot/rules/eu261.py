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
from copilot.rules.checks import check_airports, unresolved
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
COMPENSATION_LONG_EUR = 600.0  # Art. 7(1)(c): > 3,500 km non-intra-EU

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
    r"volcan(?:ic|o)",
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
    r"parts?",
    r"software",
    r"sensor",
    r"crew sick(?:ness)?",
    r"crew hour",
    r"crew timeout",
    r"crew short(?:age|ages)?",
    r"staff short(?:age|ages)?",
    r"pilot sick(?:ness)?",
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
    # LEARN: Substring matching confuses "software" with "war" and "departure"
    # with "part". Boundaries prevent that, while negation and mixed explanations
    # are deliberately sent for review rather than pretending this is language understanding.
    if re.search(r"\b(no|not|never|without)\b", clean_reason):
        return None, "A negated explanation needs factual review."
    operational = any(
        re.search(r"\b(?:" + pattern + r")\b", clean_reason)
        for pattern in NON_EXEMPT_OPERATIONAL_PATTERNS
    )
    external = any(
        re.search(r"\b(?:" + pattern + r")\b", clean_reason)
        for pattern in EXEMPT_EXTRAORDINARY_PATTERNS
    )
    if operational and external:
        return None, "Mixed operational and external causes need factual review."
    if operational:
        return (
            False,
            "The stated operational cause is generally not exempt "
            "(Wallentin-Hermann, C-549/07); the precise facts still matter.",
        )
    if external:
        return (
            True,
            "A possible extraordinary event was reported. The airline must prove "
            "causation and that all reasonable measures could not avoid the disruption.",
        )
    return None, "The stated reason needs factual review."


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
            # Unknown nationality does not establish coverage.
            return False, (
                f"Flight arrives in the EU ({arr}) from {dep}. Under Article 3(1)(b), "
                "EU261 applies if the operating airline is a Community (EU) carrier."
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
            "Intra-Community flights over 1,500 km are capped at €400 under Article 7(1)(b).",
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
    if (
        delay_minutes is not None
        and DELAY_THRESHOLD_MINUTES <= delay_minutes < LONG_HAUL_REDUCTION_DELAY_MINUTES
    ):
        rules.append("Regulation (EC) No 261/2004 Art. 7(1)(c) (> 3500 km)")
        rules.append("Regulation (EC) No 261/2004 Art. 7(2)(c) (50% reduction for delay < 4 hours)")
        return (
            300.0,
            f"Flight distance is {distance_km:,.0f} km (> 3,500 km, extra-Community). "
            f"Base compensation is €600 under Article 7(1)(c), but reduced by 50% to €300 "
            f"under Article 7(2)(c): final arrival delay was under 4 hours ({delay_minutes} mins).",
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
    """Require scope and remedy facts before applying the deterministic EU amount bands.

    Sources: EC 261/2004 Articles 3, 4, 5 and 7, plus the Commission guidance:
    https://europa.eu/youreurope/citizens/travel/passenger-rights/air/index_en.htm
    Weather keywords identify a review question, not a proven legal exemption.
    """
    if pending := check_airports(disruption, Region.EU):
        return pending
    dep, arr = disruption.flight.departure_airport, disruption.flight.arrival_airport
    if not is_eu_airport(dep) and is_eu_airport(arr) and disruption.is_eu_carrier is None:
        return unresolved(
            Region.EU,
            "Inbound EU scope depends on the operating carrier.",
            ["Is the operating airline an EU/EEA carrier?"],
        )
    in_scope, scope_reason = check_eu261_scope(disruption)
    if not in_scope:
        return CompensationResult(
            eligible=False,
            regulation=Region.EU,
            reasoning=scope_reason,
            applicable_rules=["Regulation (EC) No 261/2004 Article 3"],
        )
    kind = disruption.disruption_type
    if kind == DisruptionType.DELAY:
        if disruption.arrival_delay_minutes is None:
            return unresolved(
                Region.EU,
                "Arrival delay is needed for assessment.",
                ["What was the arrival delay at the final destination in minutes?"],
            )
        if disruption.arrival_delay_minutes < DELAY_THRESHOLD_MINUTES:
            return CompensationResult(
                eligible=False,
                regulation=Region.EU,
                reasoning="Arrival delay is below 180 minutes. Care rights may still apply.",
                applicable_rules=["CJEU C-402/07 and C-432/07 (Sturgeon)", "EU261 Article 6"],
            )
    elif kind == DisruptionType.CANCELLATION:
        notice = disruption.cancellation_notice_days
        if notice is None:
            return unresolved(
                Region.EU,
                "Cancellation notice is unknown.",
                ["How many days before departure were you told of the cancellation?"],
            )
        if notice >= 14:
            return CompensationResult(
                eligible=False,
                regulation=Region.EU,
                reasoning="At least 14 days notice: no Article 7 award; refund/rerouting remains.",
                applicable_rules=["EU261 Article 5(1)(c)(i)", "EU261 Article 8"],
            )
        if disruption.was_rerouted is None:
            return unresolved(
                Region.EU,
                "Rerouting can change cancellation eligibility.",
                ["Did the airline offer an alternative flight?"],
            )
        if disruption.was_rerouted:
            advance = disruption.rerouting_departure_advance_minutes
            planned_delay = disruption.rerouting_arrival_delay_minutes
            if advance is None or planned_delay is None:
                return unresolved(
                    Region.EU,
                    "The offered alternative's schedule is needed.",
                    ["How much earlier would it depart and later would it arrive?"],
                )
            max_advance, max_delay = (120, 240) if notice >= 7 else (60, 120)
            # LEARN: Short notice alone is insufficient. Article 5 includes
            # exceptions for suitable alternatives; its arrival limit is strict.
            if advance <= max_advance and planned_delay < max_delay:
                return CompensationResult(
                    eligible=False,
                    regulation=Region.EU,
                    reasoning="The offered schedule meets the cancellation rerouting exception.",
                    applicable_rules=["EU261 Article 5(1)(c)(ii)-(iii)"],
                )
    else:
        if disruption.volunteered_seat is True:
            return CompensationResult(
                eligible=False,
                regulation=Region.EU,
                reasoning="Voluntary surrender is governed by the agreed benefits.",
                applicable_rules=["EU261 Article 4(1)"],
            )
        questions = []
        for field, question in [
            ("volunteered_seat", "Did you voluntarily give up your seat?"),
            ("met_checkin_requirements", "Did you check in on time with valid travel documents?"),
            ("denied_due_to_overbooking", "Was boarding denied due to overbooking?"),
            ("was_rerouted", "Was alternative transportation offered?"),
        ]:
            if getattr(disruption, field) is None:
                questions.append(question)
        if questions:
            return unresolved(Region.EU, "Denied-boarding facts are missing.", questions)
        if not disruption.met_checkin_requirements or not disruption.denied_due_to_overbooking:
            return unresolved(
                Region.EU,
                "This simplified engine handles timely, documented "
                "oversales cases. Other denied-boarding circumstances need review.",
            )

    extraordinary, note = classify_extraordinary_circumstances(disruption.airline_reason)
    if kind != DisruptionType.DENIED_BOARDING and extraordinary is not False:
        questions = (
            ["What reason did the airline give for the disruption?"]
            if (not disruption.airline_reason)
            else None
        )
        result = unresolved(
            Region.EU,
            f"{scope_reason} {note} EU261 Article 5(3) requires "
            "evidence, so no automatic exemption or cash award is determined.",
            questions,
        )
        result.extraordinary_circumstances = extraordinary
        result.applicable_rules = ["EU261 Article 5(3)"]
        return result
    if kind != DisruptionType.DELAY and disruption.was_rerouted:
        if disruption.arrival_delay_minutes is None:
            return unresolved(
                Region.EU,
                "Actual arrival delay is needed for any 50% reduction.",
                ["What was the actual arrival delay on your alternative flight?"],
            )
    amount, explanation, rules = calculate_eu261_compensation_amount(
        dep,
        arr,
        disruption.arrival_delay_minutes if kind == DisruptionType.DELAY else None,
    )
    if kind != DisruptionType.DELAY and disruption.was_rerouted:
        reduction_limit = {250.0: 120, 400.0: 180, 600.0: 240}[amount]
        if disruption.arrival_delay_minutes <= reduction_limit:
            amount /= 2
            explanation += f" Article 7(2) rerouting reduction gives EUR {amount:.0f}."
            rules.append("EU261 Article 7(2) (50% rerouting reduction)")
    rules.insert(
        0,
        {
            DisruptionType.DELAY: "CJEU C-402/07 and C-432/07 (Sturgeon)",
            DisruptionType.CANCELLATION: "EU261 Article 5(1)(c)",
            DisruptionType.DENIED_BOARDING: "EU261 Article 4(3)",
        }[kind],
    )
    return CompensationResult(
        eligible=True,
        regulation=Region.EU,
        compensation_amount=amount,
        compensation_currency="EUR",
        applicable_rules=rules,
        extraordinary_circumstances=False,
        reasoning=f"{scope_reason} {explanation} {note} Estimate based on supplied facts.",
    )
