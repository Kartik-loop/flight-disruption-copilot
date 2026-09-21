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
   The LLM is strictly used for text understanding (Phase 4) and explanation.

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
   **do NOT** exempt airlines from compensation. Severe weather, ATC ground stops, and
   bird strikes **do** qualify.

5. **The Router Pattern for Jurisdiction** — `engine.py` inspects airport coordinates and
   airline registration to automatically dispatch claims to the most protective statute.
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

