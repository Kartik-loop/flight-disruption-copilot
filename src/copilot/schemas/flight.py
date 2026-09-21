"""
copilot.schemas.flight — Data models for flight disruptions.

WHAT: Pydantic models that represent a passenger's flight disruption claim.
WHY:  These are the "source of truth" data contracts. Every agent reads from
      and writes to these structures. By centralizing them here, we ensure
      the intake agent, eligibility engine, and claim drafter all speak the
      same language.
HOW:  The LLM-based intake agent extracts information from free text and
      populates a FlightDisruption object. The rules engine reads it to
      determine compensation. The drafter reads both to write a claim letter.

LEARN: Pydantic v2 models validate data on construction. If you try to create
a FlightDisruption with arrival_delay="not a number", Pydantic raises a clear
ValidationError. This is much safer than passing raw dicts around, because
bugs surface immediately instead of propagating silently through the system.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ── Enumerations ─────────────────────────────────────────────────────────
# LEARN: Enums restrict a field to a fixed set of values. This prevents the
# LLM from inventing disruption types like "turbulence" that our rules engine
# doesn't handle. When the intake agent outputs a DisruptionType, it MUST be
# one of these three values, or Pydantic rejects it.

class DisruptionType(str, Enum):
    """The three categories of disruption covered by EU261 and DOT rules."""
    DELAY = "delay"
    CANCELLATION = "cancellation"
    DENIED_BOARDING = "denied_boarding"


class Region(str, Enum):
    """
    Which regulatory regime applies.

    LEARN: EU261 and US DOT rules are completely different frameworks.
    EU261 provides fixed compensation amounts based on distance.
    US DOT rules focus on refunds for cancellations and denied-boarding
    compensation, but do NOT mandate compensation for delays alone.
    We need to know which regime to apply before checking eligibility.
    """
    EU = "eu"
    US = "us"
    OTHER = "other"  # Neither regime applies


# ── Core flight data ─────────────────────────────────────────────────────

class FlightInfo(BaseModel):
    """
    Structured representation of a single flight.

    WHY: Separating flight info from disruption info lets us reuse this
    model for the delay-prediction tool, which only needs flight details
    (no disruption context).
    """

    airline: str = Field(
        ...,
        description="IATA airline code (e.g., 'LH' for Lufthansa) or full name.",
        examples=["LH", "UA", "Ryanair"],
    )
    flight_number: Optional[str] = Field(
        None,
        description="Flight number including airline prefix, e.g., 'LH400'.",
        examples=["LH400", "UA100"],
    )
    departure_airport: str = Field(
        ...,
        description="IATA code of departure airport.",
        examples=["FRA", "JFK", "LHR"],
    )
    arrival_airport: str = Field(
        ...,
        description="IATA code of arrival airport.",
        examples=["JFK", "LAX", "CDG"],
    )
    scheduled_departure: Optional[datetime] = Field(
        None, description="Scheduled departure date and time."
    )
    scheduled_arrival: Optional[datetime] = Field(
        None, description="Scheduled arrival date and time."
    )
    flight_date: date = Field(
        ..., description="Date of the flight (used when exact times are unknown)."
    )

    # LEARN: Field(...) with ... means "required" — Pydantic will reject
    # construction if this field is missing. Field(None) means "optional,
    # defaults to None". We make airport codes required but exact times
    # optional because a passenger might not remember the scheduled times.


class FlightDisruption(BaseModel):
    """
    Complete description of a flight disruption from the passenger's perspective.

    This is the CENTRAL data object of the entire system. The intake agent
    creates it, the eligibility engine reads it, and the claim drafter uses
    it to write the letter.

    LEARN: Think of this as the "message" that flows through the LangGraph
    state. Every agent can read it and add to the state, but the core facts
    about what happened live here.
    """

    flight: FlightInfo = Field(
        ..., description="Details of the disrupted flight."
    )
    disruption_type: DisruptionType = Field(
        ..., description="What kind of disruption occurred."
    )
    arrival_delay_minutes: Optional[int] = Field(
        None,
        description="Delay at final destination in minutes. None if unknown.",
        ge=0,  # Must be >= 0
    )
    cancellation_notice_days: Optional[int] = Field(
        None,
        description="How many days before departure the cancellation was announced. "
                    "None if not a cancellation or if unknown.",
        ge=0,
    )
    was_rerouted: Optional[bool] = Field(
        None,
        description="Whether the airline offered an alternative flight.",
    )
    airline_reason: Optional[str] = Field(
        None,
        description="The reason the airline gave for the disruption (free text). "
                    "Used to check for 'extraordinary circumstances' under EU261.",
        examples=["Air traffic control strike", "Technical fault", "Bad weather"],
    )
    passenger_description: Optional[str] = Field(
        None,
        description="The passenger's own free-text description of what happened.",
    )
    is_eu_carrier: Optional[bool] = Field(
        None,
        description="Whether the airline is registered in the EU/EEA. "
                    "Relevant for EU261 scope on flights arriving in the EU.",
    )
    volunteered_seat: Optional[bool] = Field(
        None,
        description="For denied boarding: did the passenger volunteer? "
                    "Voluntary bumping has different rules than involuntary.",
    )

    # NOTE: We don't store the passenger's personal info (name, email, booking ref)
    # in this model. That would go in a separate PassengerInfo model to keep
    # concerns separated and avoid sending PII to the rules engine.
    # TODO(next): Add a PassengerInfo model for the claim letter personalization.


# ── Eligibility result ───────────────────────────────────────────────────

class CompensationResult(BaseModel):
    """
    Output of the deterministic rules engine.

    WHY: The rules engine produces structured, auditable results — not free
    text from an LLM. This model captures exactly what the engine decided
    and why, so the eligibility agent can explain it to the user and the
    claim drafter can cite specific rules.

    LEARN: Keeping the rules engine output structured (not just a string)
    means we can unit-test exact values: "for a 1200 km flight delayed
    4 hours, compensation should be exactly 250 EUR." If this were LLM
    output, we couldn't write deterministic tests.
    """

    eligible: bool = Field(
        ..., description="Whether the passenger is entitled to compensation."
    )
    regulation: Optional[Region] = Field(
        None, description="Which regulation applies (EU261 or US DOT)."
    )
    compensation_amount: Optional[float] = Field(
        None, description="Estimated compensation in EUR (EU261) or USD (DOT)."
    )
    compensation_currency: Optional[str] = Field(
        None, description="Currency code: 'EUR' for EU261, 'USD' for DOT."
    )
    reasoning: str = Field(
        ...,
        description="Step-by-step explanation of how the determination was made. "
                    "References specific regulation articles.",
    )
    applicable_rules: list[str] = Field(
        default_factory=list,
        description="List of specific regulation clauses that apply.",
    )
    extraordinary_circumstances: Optional[bool] = Field(
        None,
        description="EU261 only: whether the airline's reason qualifies as "
                    "extraordinary circumstances (which would exempt them).",
    )

    # LEARN: Pydantic deep-copies default=[], so mutable defaults are not shared
    # across instances. However, using default_factory=list is best practice for
    # explicitness and for dynamic computed values.


# ── Delay prediction ─────────────────────────────────────────────────────

class DelayPrediction(BaseModel):
    """
    Output of the delay-prediction ML model.

    WHY: The agents can call the delay predictor as a tool to give the user
    additional context ("flights on this route are delayed 35% of the time").
    This model structures that output.
    """

    probability_delayed: float = Field(
        ...,
        description="Probability (0.0–1.0) that arrival will be 15+ minutes late.",
        ge=0.0,
        le=1.0,
    )
    risk_level: str = Field(
        ...,
        description="Human-readable risk level: 'low', 'medium', or 'high'.",
    )
    features_used: dict[str, str] = Field(
        default_factory=dict,
        description="Key features and their values that drove the prediction.",
    )

    # NOTE: We intentionally keep this simple. A production system might
    # include SHAP values for each feature, confidence intervals, etc.


# ── Full agent response ──────────────────────────────────────────────────

class CopilotResponse(BaseModel):
    """
    The final response assembled by the supervisor and returned to the user.

    This bundles everything: the structured disruption data, eligibility
    determination, delay prediction (if requested), and the claim letter.
    """

    disruption: FlightDisruption = Field(
        ..., description="Validated structured disruption information."
    )
    eligibility: Optional[CompensationResult] = Field(
        None, description="Compensation eligibility determination."
    )
    delay_prediction: Optional[DelayPrediction] = Field(
        None, description="Delay probability prediction, if available."
    )
    claim_letter: Optional[str] = Field(
        None, description="Draft claim letter text."
    )
    disclaimer: str = Field(
        default=(
            "⚠️ DISCLAIMER: This analysis is for informational purposes only "
            "and does not constitute legal advice. Compensation rules have "
            "exceptions and nuances that may affect your specific case. "
            "Consult a legal professional or your national enforcement body "
            "for authoritative guidance."
        ),
        description="Legal disclaimer — always included in every response.",
    )

    # LEARN: The disclaimer has a default value, so it's automatically
    # included even if the agent forgets to set it. This is a "pit of
    # success" design: making the right thing (including a disclaimer)
    # easier than the wrong thing (omitting it).
