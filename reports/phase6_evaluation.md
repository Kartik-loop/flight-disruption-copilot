# Phase 6 — actual local API evaluation

Run: 2026-09-27T12:11:32.453767+00:00

API: `http://127.0.0.1:8000`. No graph, rules, or prediction mocks.

Inputs use the structured-form contract. Returned `collected_facts` are validated form facts, **not LLM-extracted facts**. Live narrative extraction is not verified. The missing-key probe is explicit opt-in and should only run with no key configured.

## Active model

```json
{
  "available": true,
  "data_source": "bts",
  "message": "REAL BTS DATA — trained on a historical US domestic sample. Uncalibrated estimates, not a live flight forecast.",
  "disclaimer": "This is not legal advice. This learning tool provides informational estimates only; exceptions may affect your case. Consult the relevant enforcement body for guidance."
}
```

## EU long-haul delay, five hours

HTTP 200 — PASS

EU departure; route over 3,500 km; 300-minute final-arrival delay; supplied operational cause. The below-four-hour long-haul reduction does not apply.

### Input sent

```json
{
  "disruption": {
    "flight": {
      "airline": "LH",
      "flight_number": "LH400",
      "departure_airport": "FRA",
      "arrival_airport": "JFK",
      "flight_date": "2025-03-10"
    },
    "disruption_type": "delay",
    "arrival_delay_minutes": 300,
    "airline_reason": "Technical fault",
    "declined_alternative_travel": false
  }
}
```

### Structured facts returned

```json
{
  "flight": {
    "airline": "LH",
    "flight_number": "LH400",
    "departure_airport": "FRA",
    "arrival_airport": "JFK",
    "scheduled_departure": null,
    "scheduled_arrival": null,
    "flight_date": "2025-03-10"
  },
  "disruption_type": "delay",
  "arrival_delay_minutes": 300,
  "cancellation_notice_days": null,
  "was_rerouted": null,
  "airline_reason": "Technical fault",
  "passenger_description": null,
  "is_eu_carrier": null,
  "volunteered_seat": null,
  "one_way_fare_usd": null,
  "declined_alternative_travel": false,
  "met_checkin_requirements": null,
  "denied_due_to_overbooking": null,
  "rerouting_departure_advance_minutes": null,
  "rerouting_arrival_delay_minutes": null
}
```

### Rules-engine results (including reasoning)

```json
{
  "primary": {
    "eligible": true,
    "missing_information": [],
    "review_required": false,
    "refund_eligible": null,
    "regulation": "eu",
    "compensation_amount": 600.0,
    "compensation_currency": "EUR",
    "reasoning": "Flight departs from FRA (EU/EEA jurisdiction). Under Regulation (EC) No 261/2004 Article 3(1)(a), the regulation applies to all flights departing from an airport in an EU Member State regardless of the carrier's nationality. Flight distance is 6,188 km (> 3,500 km, extra-Community). Statutory compensation is €600 pursuant to Article 7(1)(c). The stated operational cause is generally not exempt (Wallentin-Hermann, C-549/07); the precise facts still matter. Estimate based on supplied facts.",
    "applicable_rules": [
      "CJEU C-402/07 and C-432/07 (Sturgeon)",
      "Regulation (EC) No 261/2004 Art. 7(1)(c) (> 3500 km)"
    ],
    "extraordinary_circumstances": false
  },
  "additional": [
    {
      "eligible": false,
      "missing_information": [],
      "review_required": false,
      "refund_eligible": null,
      "regulation": "us",
      "compensation_amount": null,
      "compensation_currency": "USD",
      "reasoning": "Flight FRA to JFK. NO STATUTORY DELAY COMPENSATION or fixed cancellation award. Arrival delay was less than 6 hours. This does not qualify for the time-based refund rule; other significant schedule changes are not evaluated.",
      "applicable_rules": [
        "14 CFR Part 260 (Refunds)",
        "14 CFR § 260.6"
      ],
      "extraordinary_circumstances": null
    }
  ]
}
```

### Final response and letter

```json
{
  "status": "complete",
  "questions": [],
  "warnings": [],
  "steps": [
    "intake",
    "eligibility",
    "drafter",
    "finalize"
  ],
  "disclaimer": "This is not legal advice. This learning tool provides informational estimates only; exceptions may affect your case. Consult the relevant enforcement body for guidance."
}
```

```text
Dear LH Customer Relations,

Flight LH400, FRA to JFK, on 2025-03-10: delay. My actual arrival delay was 300 minutes.

Based on the supplied facts, please review my compensation claim for EUR 600.00. The assessment references: CJEU C-402/07 and C-432/07 (Sturgeon); Regulation (EC) No 261/2004 Art. 7(1)(c) (> 3500 km).

Please assess the applicable remedies without duplicate recovery. If you disagree, please provide the factual and legal basis and relevant supporting evidence.

Booking reference: [Booking reference]
Passenger: [Your name]

Thank you for reviewing my request.
Yours sincerely,
[Your name]

Draft for passenger review before sending. This is not legal advice. This learning tool provides informational estimates only; exceptions may affect your case. Consult the relevant enforcement body for guidance.
```

## US cancellation, refund only

HTTP 200 — PASS

The passenger declined travel and credits after cancellation. Refund of unused travel is separate from a fixed cash compensation award; the ticket value is not invented.

### Input sent

```json
{
  "disruption": {
    "flight": {
      "airline": "UA",
      "flight_number": "UA100",
      "departure_airport": "JFK",
      "arrival_airport": "LAX",
      "flight_date": "2025-03-10"
    },
    "disruption_type": "cancellation",
    "airline_reason": "Weather",
    "declined_alternative_travel": true
  }
}
```

### Structured facts returned

```json
{
  "flight": {
    "airline": "UA",
    "flight_number": "UA100",
    "departure_airport": "JFK",
    "arrival_airport": "LAX",
    "scheduled_departure": null,
    "scheduled_arrival": null,
    "flight_date": "2025-03-10"
  },
  "disruption_type": "cancellation",
  "arrival_delay_minutes": null,
  "cancellation_notice_days": null,
  "was_rerouted": null,
  "airline_reason": "Weather",
  "passenger_description": null,
  "is_eu_carrier": null,
  "volunteered_seat": null,
  "one_way_fare_usd": null,
  "declined_alternative_travel": true,
  "met_checkin_requirements": null,
  "denied_due_to_overbooking": null,
  "rerouting_departure_advance_minutes": null,
  "rerouting_arrival_delay_minutes": null
}
```

### Rules-engine results (including reasoning)

```json
{
  "primary": {
    "eligible": false,
    "missing_information": [],
    "review_required": false,
    "refund_eligible": true,
    "regulation": "us",
    "compensation_amount": null,
    "compensation_currency": "USD",
    "reasoning": "Flight JFK to LAX. NO STATUTORY DELAY COMPENSATION or fixed cancellation award. REFUND assessment under 14 CFR Part 260: a cancellation or significant delay (3+ hours) can trigger a refund of unused travel if the passenger declines travel and vouchers/credits. Refunds are generally due within 7 business days for credit-card payments or 20 calendar days for other payments.",
    "applicable_rules": [
      "14 CFR Part 260 (Refunds)",
      "14 CFR § 260.6"
    ],
    "extraordinary_circumstances": null
  },
  "additional": []
}
```

### Final response and letter

```json
{
  "status": "complete",
  "questions": [],
  "warnings": [],
  "steps": [
    "intake",
    "eligibility",
    "drafter",
    "finalize"
  ],
  "disclaimer": "This is not legal advice. This learning tool provides informational estimates only; exceptions may affect your case. Consult the relevant enforcement body for guidance."
}
```

```text
Dear UA Customer Relations,

Flight UA100, JFK to LAX, on 2025-03-10: cancellation.

I declined travel and vouchers/credits after the disruption. Please refund my unused ticket and applicable unused ancillary services to the original payment method under 14 CFR Part 260.

Please assess the applicable remedies without duplicate recovery. If you disagree, please provide the factual and legal basis and relevant supporting evidence.

Booking reference: [Booking reference]
Passenger: [Your name]

Thank you for reviewing my request.
Yours sincerely,
[Your name]

Draft for passenger review before sending. This is not legal advice. This learning tool provides informational estimates only; exceptions may affect your case. Consult the relevant enforcement body for guidance.
```

## US involuntary oversales, higher DOT tier

HTTP 200 — PASS

Alternative planned arrival is 150 minutes later on a domestic flight: 400% of the $300 fare, subject to the $2,150 cap effective January 22, 2025. Other Part 250 exceptions remain a limitation.

### Input sent

```json
{
  "disruption": {
    "flight": {
      "airline": "UA",
      "flight_number": "UA100",
      "departure_airport": "JFK",
      "arrival_airport": "LAX",
      "flight_date": "2025-03-10",
      "scheduled_departure": "2025-03-10T09:30:00"
    },
    "disruption_type": "denied_boarding",
    "volunteered_seat": false,
    "denied_due_to_overbooking": true,
    "met_checkin_requirements": true,
    "was_rerouted": true,
    "rerouting_arrival_delay_minutes": 150,
    "one_way_fare_usd": 300
  }
}
```

### Structured facts returned

```json
{
  "flight": {
    "airline": "UA",
    "flight_number": "UA100",
    "departure_airport": "JFK",
    "arrival_airport": "LAX",
    "scheduled_departure": "2025-03-10T09:30:00",
    "scheduled_arrival": null,
    "flight_date": "2025-03-10"
  },
  "disruption_type": "denied_boarding",
  "arrival_delay_minutes": null,
  "cancellation_notice_days": null,
  "was_rerouted": true,
  "airline_reason": null,
  "passenger_description": null,
  "is_eu_carrier": null,
  "volunteered_seat": false,
  "one_way_fare_usd": 300.0,
  "declined_alternative_travel": null,
  "met_checkin_requirements": true,
  "denied_due_to_overbooking": true,
  "rerouting_departure_advance_minutes": null,
  "rerouting_arrival_delay_minutes": 150
}
```

### Rules-engine results (including reasoning)

```json
{
  "primary": {
    "eligible": true,
    "missing_information": [],
    "review_required": false,
    "refund_eligible": null,
    "regulation": "us",
    "compensation_amount": 1200.0,
    "compensation_currency": "USD",
    "reasoning": "Flight JFK to LAX. 400% of the one-way fare, capped at $2,150, gives $1,200.00. Payment is by CASH or CHECK; vouchers are optional. Aircraft-size and other § 250.6 exceptions still need checking.",
    "applicable_rules": [
      "14 CFR § 250.5(a)(3)",
      "14 CFR § 250.8"
    ],
    "extraordinary_circumstances": null
  },
  "additional": []
}
```

### Final response and letter

```json
{
  "status": "complete",
  "questions": [],
  "warnings": [],
  "steps": [
    "intake",
    "eligibility",
    "drafter",
    "finalize"
  ],
  "disclaimer": "This is not legal advice. This learning tool provides informational estimates only; exceptions may affect your case. Consult the relevant enforcement body for guidance."
}
```

```text
Dear UA Customer Relations,

Flight UA100, JFK to LAX, on 2025-03-10: denied_boarding.

Based on the supplied facts, please review my compensation claim for USD 1200.00. The assessment references: 14 CFR § 250.5(a)(3); 14 CFR § 250.8.

Please assess the applicable remedies without duplicate recovery. If you disagree, please provide the factual and legal basis and relevant supporting evidence.

Booking reference: [Booking reference]
Passenger: [Your name]

Thank you for reviewing my request.
Yours sincerely,
[Your name]

Draft for passenger review before sending. This is not legal advice. This learning tool provides informational estimates only; exceptions may affect your case. Consult the relevant enforcement body for guidance.
```

## Missing arrival-delay fact

HTTP 200 — PASS

No final-arrival duration was supplied. A follow-up is required before determining a delay award; missing does not mean zero or three hours.

### Input sent

```json
{
  "disruption": {
    "flight": {
      "airline": "LH",
      "flight_number": "LH1000",
      "departure_airport": "FRA",
      "arrival_airport": "CDG",
      "flight_date": "2025-03-10"
    },
    "disruption_type": "delay",
    "airline_reason": "Technical fault"
  }
}
```

### Structured facts returned

```json
{
  "flight": {
    "airline": "LH",
    "flight_number": "LH1000",
    "departure_airport": "FRA",
    "arrival_airport": "CDG",
    "scheduled_departure": null,
    "scheduled_arrival": null,
    "flight_date": "2025-03-10"
  },
  "disruption_type": "delay",
  "arrival_delay_minutes": null,
  "cancellation_notice_days": null,
  "was_rerouted": null,
  "airline_reason": "Technical fault",
  "passenger_description": null,
  "is_eu_carrier": null,
  "volunteered_seat": null,
  "one_way_fare_usd": null,
  "declined_alternative_travel": null,
  "met_checkin_requirements": null,
  "denied_due_to_overbooking": null,
  "rerouting_departure_advance_minutes": null,
  "rerouting_arrival_delay_minutes": null
}
```

### Rules-engine results (including reasoning)

```json
{
  "primary": {
    "eligible": null,
    "missing_information": [
      "What was the arrival delay at the final destination in minutes?"
    ],
    "review_required": false,
    "refund_eligible": null,
    "regulation": "eu",
    "compensation_amount": null,
    "compensation_currency": null,
    "reasoning": "Arrival delay is needed for assessment.",
    "applicable_rules": [],
    "extraordinary_circumstances": null
  },
  "additional": []
}
```

### Final response and letter

```json
{
  "status": "needs_information",
  "questions": [
    "What was the arrival delay at the final destination in minutes?"
  ],
  "warnings": [],
  "steps": [
    "intake",
    "eligibility",
    "finalize"
  ],
  "disclaimer": "This is not legal advice. This learning tool provides informational estimates only; exceptions may affect your case. Consult the relevant enforcement body for guidance."
}
```

```text
No letter drafted.
```

## EU boundary: exactly three hours

HTTP 200 — PASS

The arrival-delay threshold is inclusive (at least 180 minutes), and FRA–CDG is below 1,500 km. Exactly three hours qualifies; 179 minutes would not.

### Input sent

```json
{
  "disruption": {
    "flight": {
      "airline": "LH",
      "flight_number": "LH1000",
      "departure_airport": "FRA",
      "arrival_airport": "CDG",
      "flight_date": "2025-03-10"
    },
    "disruption_type": "delay",
    "arrival_delay_minutes": 180,
    "airline_reason": "Technical fault"
  }
}
```

### Structured facts returned

```json
{
  "flight": {
    "airline": "LH",
    "flight_number": "LH1000",
    "departure_airport": "FRA",
    "arrival_airport": "CDG",
    "scheduled_departure": null,
    "scheduled_arrival": null,
    "flight_date": "2025-03-10"
  },
  "disruption_type": "delay",
  "arrival_delay_minutes": 180,
  "cancellation_notice_days": null,
  "was_rerouted": null,
  "airline_reason": "Technical fault",
  "passenger_description": null,
  "is_eu_carrier": null,
  "volunteered_seat": null,
  "one_way_fare_usd": null,
  "declined_alternative_travel": null,
  "met_checkin_requirements": null,
  "denied_due_to_overbooking": null,
  "rerouting_departure_advance_minutes": null,
  "rerouting_arrival_delay_minutes": null
}
```

### Rules-engine results (including reasoning)

```json
{
  "primary": {
    "eligible": true,
    "missing_information": [],
    "review_required": false,
    "refund_eligible": null,
    "regulation": "eu",
    "compensation_amount": 250.0,
    "compensation_currency": "EUR",
    "reasoning": "Flight departs from FRA (EU/EEA jurisdiction). Under Regulation (EC) No 261/2004 Article 3(1)(a), the regulation applies to all flights departing from an airport in an EU Member State regardless of the carrier's nationality. Flight distance is 449 km (<= 1,500 km). Statutory compensation is €250 pursuant to Article 7(1)(a). The stated operational cause is generally not exempt (Wallentin-Hermann, C-549/07); the precise facts still matter. Estimate based on supplied facts.",
    "applicable_rules": [
      "CJEU C-402/07 and C-432/07 (Sturgeon)",
      "Regulation (EC) No 261/2004 Art. 7(1)(a) (<= 1500 km)"
    ],
    "extraordinary_circumstances": false
  },
  "additional": []
}
```

### Final response and letter

```json
{
  "status": "complete",
  "questions": [],
  "warnings": [],
  "steps": [
    "intake",
    "eligibility",
    "drafter",
    "finalize"
  ],
  "disclaimer": "This is not legal advice. This learning tool provides informational estimates only; exceptions may affect your case. Consult the relevant enforcement body for guidance."
}
```

```text
Dear LH Customer Relations,

Flight LH1000, FRA to CDG, on 2025-03-10: delay. My actual arrival delay was 180 minutes.

Based on the supplied facts, please review my compensation claim for EUR 250.00. The assessment references: CJEU C-402/07 and C-432/07 (Sturgeon); Regulation (EC) No 261/2004 Art. 7(1)(a) (<= 1500 km).

Please assess the applicable remedies without duplicate recovery. If you disagree, please provide the factual and legal basis and relevant supporting evidence.

Booking reference: [Booking reference]
Passenger: [Your name]

Thank you for reviewing my request.
Yours sincerely,
[Your name]

Draft for passenger review before sending. This is not legal advice. This learning tool provides informational estimates only; exceptions may affect your case. Consult the relevant enforcement body for guidance.
```

## Error handling and prediction probes

### malformed JSON

```json
{
  "name": "malformed JSON",
  "request": "{invalid",
  "http_status": 422,
  "response": {
    "disruption": null,
    "status": "error",
    "collected_facts": {},
    "questions": [],
    "warnings": [
      "Invalid request. Check the field types and supply exactly one input mode."
    ],
    "additional_assessments": [],
    "steps": [],
    "eligibility": null,
    "delay_prediction": null,
    "claim_letter": null,
    "disclaimer": "This is not legal advice. This learning tool provides informational estimates only; exceptions may affect your case. Consult the relevant enforcement body for guidance."
  },
  "passed": true
}
```

### unknown airport

```json
{
  "name": "unknown airport",
  "request": {
    "disruption": {
      "flight": {
        "airline": "LH",
        "flight_number": "LH1000",
        "departure_airport": "ZZZ",
        "arrival_airport": "CDG",
        "flight_date": "2025-03-10"
      },
      "disruption_type": "delay",
      "arrival_delay_minutes": 180,
      "airline_reason": "Technical fault"
    }
  },
  "http_status": 200,
  "response": {
    "disruption": {
      "flight": {
        "airline": "LH",
        "flight_number": "LH1000",
        "departure_airport": "ZZZ",
        "arrival_airport": "CDG",
        "scheduled_departure": null,
        "scheduled_arrival": null,
        "flight_date": "2025-03-10"
      },
      "disruption_type": "delay",
      "arrival_delay_minutes": 180,
      "cancellation_notice_days": null,
      "was_rerouted": null,
      "airline_reason": "Technical fault",
      "passenger_description": null,
      "is_eu_carrier": null,
      "volunteered_seat": null,
      "one_way_fare_usd": null,
      "declined_alternative_travel": null,
      "met_checkin_requirements": null,
      "denied_due_to_overbooking": null,
      "rerouting_departure_advance_minutes": null,
      "rerouting_arrival_delay_minutes": null
    },
    "status": "review_required",
    "collected_facts": {
      "flight": {
        "airline": "LH",
        "flight_number": "LH1000",
        "departure_airport": "ZZZ",
        "arrival_airport": "CDG",
        "scheduled_departure": null,
        "scheduled_arrival": null,
        "flight_date": "2025-03-10"
      },
      "disruption_type": "delay",
      "arrival_delay_minutes": 180,
      "cancellation_notice_days": null,
      "was_rerouted": null,
      "airline_reason": "Technical fault",
      "passenger_description": null,
      "is_eu_carrier": null,
      "volunteered_seat": null,
      "one_way_fare_usd": null,
      "declined_alternative_travel": null,
      "met_checkin_requirements": null,
      "denied_due_to_overbooking": null,
      "rerouting_departure_advance_minutes": null,
      "rerouting_arrival_delay_minutes": null
    },
    "questions": [],
    "warnings": [],
    "additional_assessments": [],
    "steps": [
      "intake",
      "eligibility",
      "finalize"
    ],
    "eligibility": {
      "eligible": null,
      "missing_information": [],
      "review_required": true,
      "refund_eligible": null,
      "regulation": "eu",
      "compensation_amount": null,
      "compensation_currency": null,
      "reasoning": "Airport data unavailable for ZZZ. Verify the code and extend the airport table before assessment.",
      "applicable_rules": [],
      "extraordinary_circumstances": null
    },
    "delay_prediction": null,
    "claim_letter": null,
    "disclaimer": "This is not legal advice. This learning tool provides informational estimates only; exceptions may affect your case. Consult the relevant enforcement body for guidance."
  },
  "passed": true
}
```

### saved model prediction

```json
{
  "name": "saved model prediction",
  "request": {
    "disruption": {
      "flight": {
        "airline": "UA",
        "flight_number": "UA100",
        "departure_airport": "JFK",
        "arrival_airport": "LAX",
        "flight_date": "2025-03-10",
        "scheduled_departure": "2025-03-10T09:30:00"
      },
      "disruption_type": "denied_boarding",
      "volunteered_seat": false,
      "denied_due_to_overbooking": true,
      "met_checkin_requirements": true,
      "was_rerouted": true,
      "rerouting_arrival_delay_minutes": 150,
      "one_way_fare_usd": 300
    },
    "want_prediction": true
  },
  "http_status": 200,
  "response": {
    "disruption": {
      "flight": {
        "airline": "UA",
        "flight_number": "UA100",
        "departure_airport": "JFK",
        "arrival_airport": "LAX",
        "scheduled_departure": "2025-03-10T09:30:00",
        "scheduled_arrival": null,
        "flight_date": "2025-03-10"
      },
      "disruption_type": "denied_boarding",
      "arrival_delay_minutes": null,
      "cancellation_notice_days": null,
      "was_rerouted": true,
      "airline_reason": null,
      "passenger_description": null,
      "is_eu_carrier": null,
      "volunteered_seat": false,
      "one_way_fare_usd": 300.0,
      "declined_alternative_travel": null,
      "met_checkin_requirements": true,
      "denied_due_to_overbooking": true,
      "rerouting_departure_advance_minutes": null,
      "rerouting_arrival_delay_minutes": 150
    },
    "status": "complete",
    "collected_facts": {
      "flight": {
        "airline": "UA",
        "flight_number": "UA100",
        "departure_airport": "JFK",
        "arrival_airport": "LAX",
        "scheduled_departure": "2025-03-10T09:30:00",
        "scheduled_arrival": null,
        "flight_date": "2025-03-10"
      },
      "disruption_type": "denied_boarding",
      "arrival_delay_minutes": null,
      "cancellation_notice_days": null,
      "was_rerouted": true,
      "airline_reason": null,
      "passenger_description": null,
      "is_eu_carrier": null,
      "volunteered_seat": false,
      "one_way_fare_usd": 300.0,
      "declined_alternative_travel": null,
      "met_checkin_requirements": true,
      "denied_due_to_overbooking": true,
      "rerouting_departure_advance_minutes": null,
      "rerouting_arrival_delay_minutes": 150
    },
    "questions": [],
    "warnings": [
      "Uncalibrated score from a small historical sample; no live weather or airport data.",
      "Only completed, non-diverted US domestic flights were used in training.",
      "Individual categories were seen in training; route combinations may still be unseen.",
      "Delay probability does not establish compensation rights."
    ],
    "additional_assessments": [],
    "steps": [
      "intake",
      "eligibility",
      "predictor",
      "drafter",
      "finalize"
    ],
    "eligibility": {
      "eligible": true,
      "missing_information": [],
      "review_required": false,
      "refund_eligible": null,
      "regulation": "us",
      "compensation_amount": 1200.0,
      "compensation_currency": "USD",
      "reasoning": "Flight JFK to LAX. 400% of the one-way fare, capped at $2,150, gives $1,200.00. Payment is by CASH or CHECK; vouchers are optional. Aircraft-size and other § 250.6 exceptions still need checking.",
      "applicable_rules": [
        "14 CFR § 250.5(a)(3)",
        "14 CFR § 250.8"
      ],
      "extraordinary_circumstances": null
    },
    "delay_prediction": {
      "probability_delayed": 0.15574817508214528,
      "risk_level": "low",
      "features_used": {
        "airline": "UA",
        "origin": "JFK",
        "destination": "LAX",
        "scheduled_hour": "9",
        "day_of_week": "0",
        "month": "3"
      },
      "data_source": "bts",
      "limitations": [
        "Uncalibrated score from a small historical sample; no live weather or airport data.",
        "Only completed, non-diverted US domestic flights were used in training.",
        "Individual categories were seen in training; route combinations may still be unseen.",
        "Delay probability does not establish compensation rights."
      ],
      "disclaimer": "This is not legal advice. This learning tool provides informational estimates only; exceptions may affect your case. Consult the relevant enforcement body for guidance."
    },
    "claim_letter": "Dear UA Customer Relations,\n\nFlight UA100, JFK to LAX, on 2025-03-10: denied_boarding.\n\nBased on the supplied facts, please review my compensation claim for USD 1200.00. The assessment references: 14 CFR § 250.5(a)(3); 14 CFR § 250.8.\n\nPlease assess the applicable remedies without duplicate recovery. If you disagree, please provide the factual and legal basis and relevant supporting evidence.\n\nBooking reference: [Booking reference]\nPassenger: [Your name]\n\nThank you for reviewing my request.\nYours sincerely,\n[Your name]\n\nDraft for passenger review before sending. This is not legal advice. This learning tool provides informational estimates only; exceptions may affect your case. Consult the relevant enforcement body for guidance.",
    "disclaimer": "This is not legal advice. This learning tool provides informational estimates only; exceptions may affect your case. Consult the relevant enforcement body for guidance."
  },
  "passed": true
}
```

### missing LLM key

```json
{
  "name": "missing LLM key",
  "request": {
    "text": "My flight was delayed."
  },
  "http_status": 200,
  "response": {
    "disruption": null,
    "status": "error",
    "collected_facts": {},
    "questions": [],
    "warnings": [
      "No API key is configured for the selected AI provider. Use Flight details, or configure the provider key and restart the API."
    ],
    "additional_assessments": [],
    "steps": [
      "intake",
      "finalize"
    ],
    "eligibility": null,
    "delay_prediction": null,
    "claim_letter": null,
    "disclaimer": "This is not legal advice. This learning tool provides informational estimates only; exceptions may affect your case. Consult the relevant enforcement body for guidance."
  },
  "passed": true
}
```

## Legal boundary references

The exactly-three-hour test uses the inclusive final-arrival threshold in [European Commission guidance](https://europa.eu/youreurope/citizens/travel/passenger-rights/air/index_en.htm). The DOT tier and January 22, 2025 cap change are in [14 CFR 250.5 and its effective-date note](https://www.govinfo.gov/content/pkg/CFR-2025-title14-vol4/pdf/CFR-2025-title14-vol4-sec250-5.pdf). Refund conditions are in [14 CFR 260.6](https://www.ecfr.gov/current/title-14/chapter-II/subchapter-A/part-260/section-260.6).

This is not legal advice.
