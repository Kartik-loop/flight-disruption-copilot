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
   need for the part you're studying: `uv pip install -e ".[rules]"` for just
   the rules engine, or `".[all]"` for everything.

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

**A:** In Python, default mutable arguments are shared across all instances.
If we wrote `default=[]`, every `CompensationResult` would share the SAME list,
so appending to one would affect all others. `default_factory=list` creates a
**new** empty list for each instance. This is a classic Python gotcha that
Pydantic helps you avoid (it actually warns about mutable defaults).
</details>
