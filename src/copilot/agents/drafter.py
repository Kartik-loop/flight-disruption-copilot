"""Assemble a factual draft from assessed remedies without inventing legal claims.

A deterministic template is deliberate: style is less important here than
preserving amounts and uncertainty. It also makes form-based requests useful
offline. No node submits letters or needs a passenger's private booking details.
"""

from copilot.graph.state import CopilotState
from copilot.schemas.flight import DISCLAIMER, CompensationResult


def can_draft(result: CompensationResult) -> bool:
    """Only assessed remedies may become requests for money; unresolved cases stay questions."""
    return (
        not result.review_required
        and not result.missing_information
        and (
            (result.eligible is True and result.compensation_amount is not None)
            or result.refund_eligible is True
        )
    )


def drafter_agent(state: CopilotState) -> dict:
    """Quote only confirmed structured facts and keep names/booking references as placeholders."""
    disruption = state["request"].disruption
    flight = disruption.flight
    remedies = []
    for result in state["assessments"]:
        if not can_draft(result):
            continue
        if result.eligible is True:
            remedies.append(
                f"Based on the supplied facts, please review my compensation claim for "
                f"{result.compensation_currency} {result.compensation_amount:.2f}. "
                f"The assessment references: {'; '.join(result.applicable_rules)}."
            )
        if result.refund_eligible is True:
            remedies.append(
                "I declined travel and vouchers/credits after the disruption. "
                "Please refund my unused ticket and applicable unused ancillary "
                "services to the original payment method under 14 CFR Part 260."
            )
    if not remedies:
        return {"letter": None, "steps": state["steps"] + ["drafter"]}
    airline = flight.airline.replace("\n", " ").replace("\r", " ")
    number = (flight.flight_number or "[Flight number]").replace("\n", " ").replace("\r", " ")
    details = f"Flight {number}, {flight.departure_airport} to {flight.arrival_airport}, "
    details += f"on {flight.flight_date.isoformat()}: {disruption.disruption_type.value}."
    if disruption.arrival_delay_minutes is not None:
        details += f" My actual arrival delay was {disruption.arrival_delay_minutes} minutes."
    letter = "\n\n".join(
        [
            f"Dear {airline} Customer Relations,",
            details,
            *remedies,
            "Please assess the applicable remedies without duplicate recovery. If you disagree, "
            "please provide the factual and legal basis and relevant supporting evidence.",
            "Booking reference: [Booking reference]\nPassenger: [Your name]",
            "Thank you for reviewing my request.\nYours sincerely,\n[Your name]",
            "Draft for passenger review before sending. " + DISCLAIMER,
        ]
    )
    return {"letter": letter, "steps": state["steps"] + ["drafter"]}
