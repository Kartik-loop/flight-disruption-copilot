"""Request and partial-intake contracts let the workflow ask questions without inventing facts.

Partial facts belong at the intake boundary. The rules engine continues to accept
the stricter FlightDisruption model once the basic route, date, and event exist.
"""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from copilot.schemas.flight import DisruptionType, FlightDisruption, FlightInfo


class CopilotRequest(BaseModel):
    """Require exactly one input mode so prose cannot silently override a structured form."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    text: str | None = Field(None, min_length=1, max_length=12_000)
    disruption: FlightDisruption | None = None
    want_prediction: bool = False
    want_letter: bool = True
    allow_synthetic_prediction: bool = False

    @model_validator(mode="after")
    def one_input_mode(self) -> "CopilotRequest":
        """Make ambiguous or empty requests fail at the boundary before any model call."""
        if (self.text is None) == (self.disruption is None):
            raise ValueError("Supply either text or disruption, exactly one.")
        return self


class IntakeFacts(BaseModel):
    """Allow nulls during extraction; absence is information, not a reason for the LLM to guess."""

    model_config = ConfigDict(extra="forbid")
    airline: str | None = None
    flight_number: str | None = None
    departure_airport: str | None = None
    arrival_airport: str | None = None
    flight_date: date | None = None
    scheduled_departure: datetime | None = Field(None, description="Departure-airport local time.")
    scheduled_arrival: datetime | None = None
    disruption_type: DisruptionType | None = None
    arrival_delay_minutes: int | None = Field(None, ge=0)
    cancellation_notice_days: int | None = Field(None, ge=0)
    was_rerouted: bool | None = None
    airline_reason: str | None = None
    is_eu_carrier: bool | None = None
    volunteered_seat: bool | None = None
    one_way_fare_usd: float | None = Field(None, gt=0, allow_inf_nan=False)
    declined_alternative_travel: bool | None = None
    met_checkin_requirements: bool | None = None
    denied_due_to_overbooking: bool | None = None
    rerouting_departure_advance_minutes: int | None = None
    rerouting_arrival_delay_minutes: int | None = None

    def missing_questions(self) -> list[str]:
        """Ask only for absent basic facts here; legal follow-ups belong to the rules engine."""
        return [
            question
            for field, question in {
                "airline": "Which airline operated the flight?",
                "departure_airport": "What was the departure airport's IATA code?",
                "arrival_airport": "What was the destination airport's IATA code?",
                "flight_date": "What was the flight date, including the year?",
                "disruption_type": "Was this a delay, cancellation, or denied boarding?",
            }.items()
            if getattr(self, field) is None or getattr(self, field) == ""
        ]

    def to_disruption(self) -> FlightDisruption:
        """Validate again against the core model before facts cross into legal evaluation."""
        values = self.model_dump(exclude_none=True)
        flight_fields = set(FlightInfo.model_fields)
        flight = FlightInfo(**{key: value for key, value in values.items() if key in flight_fields})
        return FlightDisruption(
            flight=flight,
            **{key: value for key, value in values.items() if key not in flight_fields},
        )
