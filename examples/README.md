# Phase 4 examples

These are fictional structured inputs for running the real LangGraph without
an API key. Run the commands from the project root after installing `[agents,ml,dev]`.

| Input | Expected result |
|---|---|
| `eu_delay.json` | EUR 250 estimate for a four-hour FRA–CDG delay with a technical cause; draft letter |
| `us_denied_boarding.json` | USD 1,200 estimate from a USD 300 fare and an offered arrival 150 minutes late; draft letter |

```bash
python -m copilot.graph --file examples/eu_delay.json
python -m copilot.graph --file examples/us_denied_boarding.json
python -m copilot.graph --file examples/us_denied_boarding.json --predict
```

For the last command, first train the model. The current checked model uses real
BTS data and needs no synthetic opt-in. If you intentionally train a synthetic
fallback instead, add `--allow-synthetic-prediction` for a labelled teaching score;
otherwise the graph returns a warning while preserving the rules result and draft.

Try removing `one_way_fare_usd` from a copy of the US example: the graph asks
for the fare and does not invent a payout. Try changing the EU reason to
`Severe weather`: the graph requests review rather than automatically accepting
the airline's exemption claim. `--no-letter` omits the drafter node.

Actual and planned arrival delays are separate. For US bumping, set
`rerouting_arrival_delay_minutes` from the alternative's **offered schedule**;
do not substitute its eventual actual arrival. Departure schedule times used
for ML are local to the departure airport.

To try free text, configure a valid provider key and available model in `.env`,
then use `--text`. Free text is sent to that provider. No live API call was made
during phase-4 verification because no key was configured.

Every result and claim draft includes: **This is not legal advice.**


## Phase 6: repeat the live API evaluation

With the API running, execute `python examples/evaluate_api.py` from the project root.
If that server has no provider key, add `--check-missing-key` to exercise its safe error.
The five inputs are in `phase6_scenarios.json`. Full actual requests and responses,
including facts and letters, are saved in `../reports/phase6_evaluation.md` and JSON.
The saved model now uses real BTS data; synthetic opt-in is unnecessary for that model.
This evaluates structured-form requests, not live LLM extraction. This is not legal advice.
