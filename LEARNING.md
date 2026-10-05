# 📚 LEARNING.md — Concepts, Reading Order & Self-Check Questions

This document grows with each phase. After studying a phase, try the self-check
questions before moving on. Answers are in collapsible sections.

---

## Phase 1: Project Scaffold, Config & Schemas

### Key concepts introduced

1. **Pydantic v2 for data validation** — Define Python classes that automatically
   validate their inputs. If you create a `FlightDisruption` with the wrong type
   for a field, you get a clear error immediately. This replaces fragile dict-passing.

2. **Pydantic Settings for configuration** — Instead of scattered `os.getenv()`
   calls, all configuration lives in a single `Settings` class that reads from
   environment variables and `.env` files. Type-safe, centralized, testable.

3. **Enums for constrained values** — `DisruptionType` and `Region` are enums,
   not bare strings. This prevents typos and makes the valid values discoverable
   in code. If you try `DisruptionType("turbulence")`, Python raises an error.

4. **The "shared language" pattern** — All agents communicate via Pydantic models
   defined in `schemas/`. This is like defining a protocol: everyone agrees on
   the data format, so agents are loosely coupled and independently testable.

5. **Optional dependency groups** — `pyproject.toml` splits dependencies into
   groups (`ml`, `agents`, `api`, `ui`, `dev`). You can install only what you
   need for the part you're studying: `uv pip install -e ".[dev]"` for development
   tools, or `uv pip install -e ".[all]"` for everything.

### Files to read (in order)

1. [`pyproject.toml`](pyproject.toml) — Project metadata and dependency groups
2. [`.env.example`](.env.example) — All configurable environment variables
3. [`src/copilot/schemas/flight.py`](src/copilot/schemas/flight.py) — The core
   data models. Read every `LEARN:` comment.
4. [`src/copilot/config.py`](src/copilot/config.py) — Settings management
5. [`tests/test_schemas.py`](tests/test_schemas.py) — How to test Pydantic models
6. [`tests/test_config.py`](tests/test_config.py) — How to test configuration

### Self-check questions

<details>
<summary><strong>Q1: Why do we use Pydantic models instead of plain dicts?</strong></summary>

**A:** Three reasons: (1) **Validation** — Pydantic checks types and constraints
at construction time, so bugs surface immediately. A dict silently accepts
`{"delay": "yes"}` where a number was expected. (2) **Documentation** — The model
definition IS the documentation. Field descriptions, types, and examples are
all in one place. (3) **Serialization** — `.model_dump_json()` and
`.model_validate_json()` handle JSON conversion automatically, which we need
for the API and LLM tool calls.
</details>

<details>
<summary><strong>Q2: What's the difference between <code>Field(...)</code> and <code>Field(None)</code>?</strong></summary>

**A:** `Field(...)` (or just listing the type without a default) makes a field
**required** — Pydantic raises `ValidationError` if it's missing. `Field(None)`
makes a field **optional** with a default of `None`. We make core facts like
`airline` required but contextual info like `airline_reason` optional, because
a passenger might not know why their flight was disrupted.
</details>

<details>
<summary><strong>Q3: Why does <code>CompensationResult</code> use <code>default_factory=list</code> instead of <code>default=[]</code>?</strong></summary>

**A:** Pydantic deep-copies mutable defaults per instance, so `default=[]` would
not actually be shared across instances, and Pydantic does not warn about it.
However, using `default_factory=list` is good practice for two reasons:
(1) **Explicitness** — it clearly signals that a fresh container is generated for
each instance, avoiding ambiguity for developers accustomed to standard Python's
mutable default trap; and (2) **Fresh computed values** — `default_factory` supports
callables (e.g., `list`, `dict`, `datetime.now`, `uuid4`) to compute fresh default
</details>

---

## Phase 2: Deterministic EU261 / US DOT Rules Engine

### Key concepts introduced

1. **Deterministic rules vs. LLM guesswork** — Laws are deterministic algorithms with
   statutory thresholds (e.g. €250 for flights $\le$ 1,500 km delayed $\ge$ 3 hours). If an
   LLM calculates compensation, it suffers from hallucinations, numerical rounding bugs,
   and unpredictable responses. We keep legal rules in pure, unit-tested Python functions.
   The LLM is used for text extraction in Phase 4; rule explanations remain deterministic.

2. **Great-Circle Distance via Haversine (EU261 Art. 7(4))** — Compensation tiers depend on
   spherical distance between airports. The CJEU held in *Bossen v Brussels Airlines*
   (Case C-559/16) that distance is measured strictly between the initial departure
   and final destination using the great-circle method, regardless of connecting legs flown.

3. **The Fundamental US vs. EU Regulatory Divergence** —
   - **Europe (Regulation EC 261/2004 & CJEU Sturgeon)**: Provides statutory fixed cash
     compensation (€250, €400, or €600) for delays of 3+ hours unless extraordinary
     circumstances apply.
   - **United States (14 CFR Part 250 & 260)**: There is **NO federal statutory cash
     compensation for delays**. Federal law only mandates involuntary denied boarding
     compensation (up to $2,150) and full prompt refunds if a passenger declines travel
     after a "significant delay" (3+ hours domestic, 6+ hours international).

4. **"Extraordinary Circumstances" (EU261 Art. 5(3))** — Under the CJEU *Wallentin-Hermann*
   test (Case C-549/07), an event exempts the airline only if it is (a) not inherent in the
   normal exercise of the activity, and (b) beyond the carrier's actual control. Technical
   malfunctions, engine part wear, and crew shortages are inherent operational risks and
   generally do not establish an exemption. Severe weather, ATC ground stops, and
   bird strikes may qualify, but causation and reasonable measures require evidence.

5. **The Router Pattern for Jurisdiction** — `engine.py` inspects airport coordinates and
   airline registration to select candidate regimes. Phase 4 retains separate results
   when both regimes may apply, without ranking currencies or combining awards.
   For example, a US airline departing Paris for New York is bound by EU261 because it
   departed from an EU airport (Art. 3(1)(a)).

### Files to read (in order)

1. [`src/copilot/rules/airports.py`](src/copilot/rules/airports.py) — Airport geodata & Haversine formula
2. [`src/copilot/rules/eu261.py`](src/copilot/rules/eu261.py) — European Regulation EC 261/2004 engine
3. [`src/copilot/rules/dot.py`](src/copilot/rules/dot.py) — US DOT (14 CFR 250 & 260) engine
4. [`src/copilot/rules/engine.py`](src/copilot/rules/engine.py) — Jurisdiction router
5. [`tests/test_airports.py`](tests/test_airports.py) — Distance & geodata tests
6. [`tests/test_eu261.py`](tests/test_eu261.py) — EU261 unit test suite
7. [`tests/test_dot.py`](tests/test_dot.py) — US DOT unit test suite
8. [`tests/test_engine.py`](tests/test_engine.py) — Router tests

### Self-check questions

<details>
<summary><strong>Q1: Why should an LLM never calculate EU261 compensation amounts directly?</strong></summary>

**A:** Legal rules are deterministic conditional algorithms, not probabilistic text tasks.
An LLM can hallucinate numbers, invent exceptions, miscalculate distances, or fail to apply
statutory caps (such as the intra-EU €400 cap or 50% reduction clause). By implementing the
rules in pure Python, we guarantee 100% reproducible, auditable, and unit-tested decisions.
</details>

<details>
<summary><strong>Q2: If a flight from Paris (CDG) to Réunion Island (RUN, ~9,360 km) is delayed by 5 hours due to a technical breakdown, why is compensation €400 and not €600?</strong></summary>

**A:** Two reasons:
(1) **Article 7(1)(b) Intra-EU Cap**: Réunion is an EU Outermost Region (France). Article 7(1)(b)
explicitly mandates €400 for **all intra-Community flights exceeding 1,500 km**, regardless
of total distance. The €600 tier in Article 7(1)(c) only applies to extra-Community (non-intra-EU) flights.
(2) **Technical breakdown liability**: Under CJEU Case C-549/07 (*Wallentin-Hermann*), technical
defects are inherent in airline operations and do not qualify as extraordinary circumstances.
</details>

<details>
<summary><strong>Q3: If a flight from New York to Los Angeles is delayed by 6 hours, does the passenger get statutory cash compensation under US DOT rules?</strong></summary>

**A:** **No.** United States federal law has no statutory fixed monetary compensation for delays.
Under the April 2024 DOT Final Rule (14 CFR Part 260), a 6-hour delay qualifies as a "significant delay"
(3+ hours domestic), which entitles the passenger to a **100% prompt refund** of their ticket if they
choose not to travel. But if the passenger takes the flight, federal law awards $0 in cash compensation.
</details>

---

## Phase 3: Data, Exploration, and Delay Prediction

### Key concepts introduced

1. **Define the population before the target.** We predict arrival delay of at
   least 15 minutes among completed, non-diverted US domestic reporting-carrier
   flights. Cancellations and missing arrival outcomes are excluded, not labelled
   “on time.” That makes this model narrower than an all-disruption predictor.
2. **Prevent leakage with a feature allowlist.** The model receives airline,
   origin, destination, scheduled local departure hour, weekday, and month.
   Actual departure delay and recorded delay causes are unavailable before
   departure. They may correlate strongly with arrival delay but would answer
   a different question from the one this model is meant to answer.
3. **Sample the complete file.** BTS files can be sorted by carrier. Reading the
   first 20,000 rows could therefore select only a few airlines. Random priorities
   give all usable rows a chance while keeping memory use bounded by a chunk and
   a small retained sample. A fixed seed makes the sample reproducible.
4. **Evaluate forward in time.** January–February 2025 train the model; March is
   held out. A random split would mingle future and past conditions. One-hot
   category encoding is fitted only on training data; unseen categories do not
   crash prediction. The entire preprocessing/model pipeline is saved together.
5. **Compare against a trivial baseline.** Accuracy is the fraction correct.
   Precision is the fraction of delay alerts that are correct. Recall is the
   fraction of real delays detected. ROC-AUC measures how well scores rank
   delayed flights above on-time flights, across decision thresholds. Always
   predicting “on time” has zero delay recall, even if its accuracy looks high.
6. **Preserve provenance and uncertainty.** Dataset and model metadata record
   source labels, hashes, dates, settings, and versions. If the optional network
   fallback is used, every output says synthetic. Its scores test the plumbing,
   not real-world forecasting. Model probabilities are not yet calibrated.

### Files to read (in order)

1. `src/copilot/ml/data.py` — official archives, chunked sampling, cleaning,
   target construction, synthetic fallback, and provenance.
2. `src/copilot/ml/train.py` — chronological split, preprocessing pipeline,
   LightGBM, baseline, metrics, and persistence.
3. `tests/test_ml.py` — leakage, missing outcomes, sampling across chunk
   boundaries, time separation, fallback labels, and reloading the saved model.
4. `models/evaluation.md` — generated exploration and actual held-out results.
5. `models/model_metadata.json` — exact data source, versions, dates, and scores.

### Try it yourself

Run the two commands in the README's phase 3 section, then open the evaluation
report. Compare model recall with the baseline before looking at accuracy.
Inspect the saved date ranges to confirm every training flight precedes the test
month. For an experiment, use a separate `--output-dir` and different months;
avoid repeatedly tuning parameters on the same held-out test month.

### Self-check questions

<details>
<summary><strong>Q1: Why is actual departure delay excluded even though it predicts arrival delay well?</strong></summary>

**A:** It is not known when the passenger is planning a flight. Including it
would leak future information into a pre-departure prediction. Arrival delay
itself is allowed only as the target we learn to predict, never as an input.
</details>

<details>
<summary><strong>Q2: Why save the encoder with the model, and fit it only on earlier months?</strong></summary>

**A:** The encoder determines which input columns represent which categories.
Recreating it later can change those meanings. Learning it from the test month
also gives preprocessing access to supposedly unseen data. A single fitted
pipeline keeps training and inference consistent and the time split honest.
</details>

<details>
<summary><strong>Q3: A model has 80% accuracy and the always-on-time baseline has 81%. Is the model useless?</strong></summary>

**A:** Not necessarily. It may identify delayed flights that the baseline never
finds. Inspect precision, recall, and ROC-AUC, then consider the cost of false
alerts and missed delays. The test month alone cannot prove general usefulness;
additional time periods and probability calibration are later improvements.
</details>

### Trade-offs and next steps

- Three months keep this exercise manageable but do not cover annual seasonality.
- The fixed 0.5 threshold is deliberately not optimized on the test set. A future
  training/validation/test time split would let us choose a threshold honestly.
- Sampling equal counts per month is useful for this exercise; the aggregate
  sample is not weighted to represent annual flight volume.
- Future work: calibration, additional seasons, evaluation by airline/route,
  and the phase 4 prediction tool. Risk predictions do not decide compensation.

**This is not legal advice.**

---

## Phase 4: LangGraph Specialists and Safe Boundaries

### Key concepts introduced

1. **State is the shared notebook.** `CopilotState` carries the request, facts,
   assessments, optional prediction, draft, and completed steps. Nodes return
   changed fields; LangGraph merges them. These nodes run sequentially, so lists
   are replaced explicitly rather than accumulated through parallel reducers.
2. **Conditional edges express control flow.** The supervisor chooses intake,
   eligibility, optional prediction, supported drafting, or finalization. Each
   specialist runs at most once. A recursion limit is a second guard against
   accidental cycles, not the mechanism used to finish normal requests.
3. **A specialist need not be an LLM call.** Intake benefits from language
   understanding. Routing, legal arithmetic, and preserving exact amounts do
   not. This implementation uses a deterministic drafting template so unknown
   booking details remain placeholders and an LLM cannot embellish the award.
4. **Partial input deserves a partial answer.** `IntakeFacts` permits nulls;
   `FlightDisruption` still requires the basic route, date, airline, and event.
   Missing basic facts stop intake with questions. Missing legal facts produce
   unresolved assessments. `eligible=None` means unknown, not a denial.
5. **Tools need domain boundaries.** `predict_delay` verifies source labels,
   matching artifact hashes, available features, and supported categories. It
   refuses synthetic output unless demo mode is explicit. That label survives
   in the final response, and prediction never affects legal arithmetic.
6. **Dependency injection makes tests honest.** Tests run the real compiled
   graph with controlled extractor responses. Other tests load a tiny trained
   model. No API credentials are necessary, but these tests cannot establish
   real-provider extraction quality or connectivity.
7. **Failure is part of the contract.** Provider exceptions become a bounded
   error without exposing diagnostic secrets. Optional ML failures become
   warnings while rules results remain available. Successful, incomplete,
   review-required, and error responses all carry the disclaimer.

### Files to read (in order)

1. `src/copilot/schemas/requests.py` — exclusive request modes and nullable intake facts.
2. `src/copilot/graph/state.py` — fields shared between nodes.
3. `src/copilot/agents/llm.py` and `intake.py` — lazy provider construction,
   fact-only extraction, validation, and failure handling.
4. `src/copilot/rules/checks.py` and `engine.py` — unresolved results and
   separate assessments when both regimes may apply.
5. `src/copilot/agents/eligibility.py`, `predictor.py`, and `drafter.py` — small
   specialists with deliberately different responsibilities.
6. `src/copilot/ml/predict.py` — model provenance, synthetic opt-in, local time,
   and training-coverage requirements.
7. `src/copilot/agents/supervisor.py` and `graph/workflow.py` — routing and wiring.
8. `tests/test_workflow.py`, `test_rule_uncertainty.py`, `test_predict_tool.py`,
   and `test_providers.py` — behavior at the boundaries rather than only happy paths.
9. `examples/README.md` — commands that run without an API key.

### Rules corrections needed before agent integration

The earlier tests made several unstated assumptions. Phase 4 makes those facts
explicit: carrier nationality, cancellation notice, alternate schedules, actual
fares, voluntary surrender, and oversales/check-in conditions. Unknown airport
coordinates no longer produce an invented distance. UK261 is not treated as EU261.

Word boundaries avoid matching `war` inside “software” and `part` inside
“departure.” Negation or mixed causes trigger review. A reported external cause
is not proof of an EU exemption. Cancellation rerouting has its own exceptions
and reduction checks; US bumping uses the offered alternative's planned arrival,
including strict tier boundaries. US refunds and cash awards have separate fields.

The airport list, legal scope, and exception handling remain intentionally
limited. In particular, historical US caps, UK261, complex connections, and
all forms of significant schedule changes are not implemented. The program is
an informational learning tool, not a complete legal adjudication system.

### Self-check questions

<details>
<summary><strong>Q1: Why is the supervisor deterministic if this is an agent workflow?</strong></summary>

**A:** The useful order is already known. Facts must precede assessment, and a
supported assessment must precede a monetary claim draft. A language model
would add uncertainty and cost to that routing policy. LangGraph still executes
real specialist nodes and conditional edges, which you can inspect and test.
</details>

<details>
<summary><strong>Q2: Why can't an unknown alternative-arrival time mean “no alternative”?</strong></summary>

**A:** Those are different facts with different consequences. The passenger may
have received an alternative but forgotten its time. Treating unknown as none
can inflate an award. The schema preserves null, and the engine asks a question
instead of assigning an invented delay or fare.
</details>

<details>
<summary><strong>Q3: Do the offline graph tests prove that a real LLM extracts every claim correctly?</strong></summary>

**A:** No. They prove how the graph behaves for controlled valid, incomplete,
invalid, and failed extraction outputs. Live evaluation needs a configured
provider and representative narratives. Pydantic validates shape and values;
it cannot prove that a plausible extracted fact appeared in the original text.
</details>

### Verification and next phase

The phase-4 suite passes 106 tests. Both real provider adapters can construct
structured extractors without a network request. The two example commands run
the actual graph; the US demo also reloads the saved phase-3 model and labels
its output synthetic. No live provider request was made because no key is configured.

Next is phase 5: FastAPI and Streamlit around this same request/response contract.
Follow-up answers currently require resubmitting corrected structured facts;
there is no persistent multi-turn state or automatic claim submission.

References: [LangGraph graph API](https://docs.langchain.com/oss/python/langgraph/graph-api),
[OpenAI structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs),
[EU passenger guidance](https://europa.eu/youreurope/citizens/travel/passenger-rights/air/index_en.htm),
[US denied-boarding amounts](https://www.ecfr.gov/current/title-14/chapter-II/subchapter-A/part-250/section-250.5).

**This is not legal advice.**


## Phase 5 — HTTP boundary and passenger interface

The API validates requests before invoking the same graph as the CLI. A synchronous
endpoint runs blocking work in FastAPI's thread pool. Transport success differs
from domain completion: a valid request can still need more facts. Error handlers
avoid returning raw descriptions, provider details, or validation inputs.

Streamlit forms batch edits until submission. Session state keeps the latest
assessment, while the edit button copies extracted facts into ordinary fields.
Blank numeric inputs and “Not sure” become null, rather than invented zeroes or
false answers. Clearing an old result before submission prevents stale awards
from surviving a failed request. The server-side HTTP client has a timeout and
no automatic retries. There is no cross-session claim history or automatic sending.

Read in order:
1. `src/copilot/api/main.py` — request validation, thread-pool endpoint, safe errors.
2. `src/copilot/api/client.py` — timeout and response validation.
3. `ui/app.py` — form, session state, prefill, uncertainty and download display.
4. `tests/test_api.py`, `tests/test_api_client.py`, `tests/test_ui.py` — HTTP and UI behavior.

### Self-check questions

1. **Why can HTTP 200 contain needs_information?** The service processed a valid
   request successfully, but the passenger has not supplied enough facts to decide.
2. **Why preserve null instead of using zero minutes or No?** Absence of evidence
   is not an answer; a fabricated value can change compensation eligibility.
3. **Why avoid automatic retries?** A timed-out provider call may already have
   incurred cost. Repeating it automatically could create duplicate paid work.

References: [FastAPI error handling](https://fastapi.tiangolo.com/tutorial/handling-errors/)
and [Streamlit AppTest](https://docs.streamlit.io/develop/api-reference/app-testing/st.testing.v1.apptest).

Phase 6 will evaluate the complete flow on five scenarios and finish integration
polish. Live provider extraction remains unverified without a configured key.
**This is not legal advice.**

Verification: 118 tests pass (including API validation, safe server errors,
client timeouts and failures, form submission, stale-result removal, fact prefill,
and synthetic labels). Live local HTTP requests returned EUR 250 for the EU
example and USD 1,200 for the US example. Streamlit's health endpoint returned
200 and its form loaded in the browser. One upstream LangGraph deprecation
warning remains; no live LLM extraction was exercised.


## Phase 6 — Real data, live evaluation and final polish

The March BTS download succeeded on retry. The active model now uses 60,000 real
flights: January and February train it, March tests it. Metadata explicitly records
`source: real`, `data_source: bts`, `synthetic: false` in the manifest, and the three
archive URLs/hashes. The earlier phase-3 and phase-4 notes describe historical
synthetic checkpoints; they no longer describe the active model.

Real data exposed a useful lesson: 80.22% accuracy is slightly worse than the
80.295% always-on-time baseline. Recall is only 1.29%, precision 43.59%, and ROC-AUC
0.6187. We did not tune against the held-out month to improve the headline score.
A future experiment needs a separate time-ordered validation period for threshold
selection and probability calibration, followed by an untouched later test period.

Unit tests isolate rules, thresholds, and failure modes. End-to-end checks additionally
verify that the running HTTP service validates and serializes inputs correctly, invokes
the real graph, loads the saved model, and returns the right questions or letter.
Browser verification checks the displayed model source and connects the form to the
running API. It also exposed a stale Streamlit module import that required restarting
the UI process—something isolated unit tests cannot reveal.

Five scenarios passed through real HTTP: EU long-haul delay, US refund only,
involuntary US oversales, missing arrival-delay facts, and exactly three hours of
EU arrival delay. Full inputs, returned facts, reasons and letters are recorded in
`reports/phase6_evaluation.md` and raw JSON. They use structured form facts, not live
LLM extraction. No provider key is configured, so live extraction remains unverified.
The API also passed malformed-input, missing-key, unknown-airport, and real-model
prediction checks. Missing facts remain questions; unknown airport geography becomes
review; missing provider credentials produce an actionable error without leaking secrets.

Read in order:
1. `models/model_metadata.json` and `models/evaluation.md` — provenance and honest metrics.
2. `examples/phase6_scenarios.json` — inputs and independently specified expectations.
3. `examples/evaluate_api.py` and `reports/phase6_evaluation.md` — real HTTP evidence.
4. `src/copilot/api/status.py`, `ui/app.py`, and `tests/test_model_status.py` — visible source labels.

### Self-check questions

1. **What can a passing unit suite miss that a live API/UI check finds?** Process
   configuration, stale imports, serialization, networking, saved artifact loading,
   and whether the passenger actually sees the correct result and uncertainty.
2. **Does 80.22% accuracy prove this model is useful?** No. The baseline reaches
   80.295%, and the model catches only 1.29% of delays at its fixed threshold.
   ROC-AUC above 0.5 indicates some ranking signal, not calibrated individual risk.
3. **Why do the five successful form scenarios not prove LLM extraction quality?**
   Form data bypasses extraction. Live narratives need separate provider evaluation;
   schema validation alone cannot detect a plausible but invented fact.

Verification: **127 tests passed**, all five live scenarios and four probes passed,
and repository lint passed. One upstream LangGraph pending-deprecation warning remains.
This is a learning demo: small airport table, incomplete legal exceptions, UK261
unsupported, no persistent request history, no authentication, and no automatic sending.
**This is not legal advice.**

## UI refinement — Streamlit presentation

The existing Streamlit form now uses local CSS and a light sage/ivory theme.
All assessment fields and the API contract stay the same. Paired inputs reduce
vertical scanning, while cards separate intake from results. No remote fonts,
background video, or frontend build system are required.

Read `ui/styles.css` for system fonts, translucent surfaces, focus feedback,
250ms transitions, result-entry keyframes, and reduced-motion support. Read
`ui/app.py` for the static HTML header and the truthful pending message. CSS uses
Streamlit test IDs rather than generated class names; check those selectors after
framework upgrades. `st.container(key="results")` gives the result a stable scope.

Self-check:
1. **Why animate opacity and transforms?** They avoid repeatedly changing layout
   dimensions and moving nearby controls during the animation.
2. **Why is loading copy not a sequence of agent stages?** The API sends only a
   final response; claiming stage progress would invent information.
3. **Why retain a reduced-motion alternative?** Motion is optional feedback;
   the operating system preference should not prevent access to any result.

The source banner, synthetic warning, and legal disclaimer remain visible.
This is not legal advice.


## Deployment repair — Community Cloud

Cloud selected Poetry for `pyproject.toml` and rejected the self-referencing `all`
extra. It now contains an explicit union, covered by a packaging test. The root
`requirements.txt` selects a pip-compatible editable installation of the package
and the runtime extras needed for Streamlit.

A second deployment boundary matters: localhost means the cloud container, not
the developer's laptop. Without `COPILOT_API_URL`, the UI runs the same graph
in-process. With an explicit URL, it uses HTTP and does not silently fall back.
A checkout without the ignored model binary reports unavailable, preserving
rules assessments without falsely advertising prediction readiness.

Self-check:
1. **Why install the project itself?** The `src/` package must be importable from `ui/app.py`.
2. **Why not start a background API automatically?** A shared in-process graph avoids
   port, lifecycle and process-management problems on a single-service host.
3. **Does committed metadata prove a model is available?** No. A matching trusted
   binary is required; metadata alone cannot produce predictions.
