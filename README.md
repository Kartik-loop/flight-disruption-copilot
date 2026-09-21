# ✈️ Flight Disruption Copilot

A multi-agent AI system that helps air passengers understand their compensation
rights when flights are delayed, cancelled, or they're denied boarding.

> **⚠️ Disclaimer:** This is a learning project. It provides informational
> analysis only and does **not** constitute legal advice. Always consult a
> legal professional for your specific situation.

## What it does

1. **Describe your disruption** — in plain language or via a structured form
2. **Get a compensation assessment** — the system checks EU261 (Europe) and
   US DOT rules using a deterministic rules engine (not LLM guesswork)
3. **Receive a draft claim letter** — ready to send to the airline
4. **See delay risk predictions** — an ML model estimates how likely your
   route is to experience delays

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                     Supervisor Agent                         │
│                  (routes between specialists)                │
└───────┬──────────────┬──────────────┬──────────────┬─────────┘
        │              │              │              │
   ┌────▼────┐   ┌─────▼─────┐  ┌────▼────┐  ┌─────▼─────┐
   │ Intake  │   │Eligibility│  │  Delay  │  │  Claim    │
   │ Agent   │   │  Agent    │  │Predictor│  │  Drafter  │
   │         │   │           │  │  (ML)   │  │           │
   │ Text →  │   │ Rules     │  │         │  │ Facts →   │
   │ Struct  │   │ Engine    │  │ Model   │  │ Letter    │
   └─────────┘   └─────┬─────┘  └─────────┘  └───────────┘
                        │
                  ┌─────▼─────┐
                  │ EU261/DOT │  ← Deterministic Python rules
                  │ Rules     │    with unit tests
                  └───────────┘
```

### Key design decisions

- **Rules are deterministic, not LLM-driven.** EU261 and DOT compensation
  rules are laws with specific conditions. The LLM extracts facts and explains
  results; plain Python with unit tests applies the rules.
- **Multi-agent over monolithic chain.** Each agent is focused and testable.
- **LLM provider is configurable.** Switch between OpenAI and Google Gemini
  via environment variables.

## Setup

```bash
# Clone the repo
git clone <repo-url>
cd flight-disruption-copilot

# Create a virtual environment and install dependencies
uv venv
source .venv/bin/activate      # On macOS/Linux
uv pip install -e ".[all]"     # Install all dependencies

# Copy environment template and add your keys
cp .env.example .env
# Edit .env with your API key(s)

# Run tests
pytest

# Start the API server
uvicorn copilot.api.main:app --reload

# Start the Streamlit UI
streamlit run ui/app.py
```

## Project structure

```
flight-disruption-copilot/
├── README.md              ← You are here
├── LEARNING.md            ← Learning guide: concepts, reading order, exercises
├── pyproject.toml         ← Project config and dependencies
├── .env.example           ← Template for environment variables
│
├── src/copilot/
│   ├── schemas/           ← Pydantic data models (the shared language)
│   │   └── flight.py      ← FlightDisruption, CompensationResult, etc.
│   ├── config.py          ← Settings from environment variables
│   ├── rules/             ← Deterministic compensation rules
│   │   ├── eu261.py       ← EC 261/2004 regulation
│   │   ├── dot.py         ← US DOT rules
│   │   └── engine.py      ← Router: picks EU261 or DOT based on region
│   ├── ml/                ← Delay prediction ML model
│   │   ├── data.py        ← Data download and preparation
│   │   ├── train.py       ← Model training pipeline
│   │   └── predict.py     ← Prediction interface for agents
│   ├── agents/            ← LangGraph agent implementations
│   │   ├── intake.py      ← Free text → structured FlightDisruption
│   │   ├── eligibility.py ← Runs rules engine, explains results
│   │   ├── drafter.py     ← Writes claim letters
│   │   └── supervisor.py  ← Routes between agents
│   ├── graph/             ← LangGraph workflow definition
│   │   └── workflow.py    ← State graph wiring
│   └── api/               ← FastAPI web API
│       └── main.py        ← API endpoints
│
├── ui/
│   └── app.py             ← Streamlit demo UI
│
├── data/                  ← Raw and processed data (gitignored)
├── models/                ← Trained model artifacts (gitignored)
├── notebooks/             ← Optional EDA notebooks
└── tests/                 ← pytest test suite
    ├── test_schemas.py
    ├── test_config.py
    ├── test_eu261.py
    ├── test_dot.py
    └── ...
```

## Tech stack

| Component | Technology |
|-----------|-----------|
| Multi-agent system | LangGraph |
| Data validation | Pydantic v2 |
| Web API | FastAPI |
| Demo UI | Streamlit |
| ML model | scikit-learn + LightGBM |
| Training data | US BTS On-Time Performance |
| LLM providers | OpenAI GPT-4o / Google Gemini (configurable) |
| Testing | pytest |

## Phases

This project is built incrementally:

1. ✅ **Scaffold** — Project structure, config, schemas, README
2. ✅ **Rules engine** — Deterministic EU261/DOT rules with unit tests
3. 🔲 **ML model** — Delay prediction model training and evaluation
4. 🔲 **Agents** — LangGraph multi-agent workflow
5. 🔲 **API + UI** — FastAPI endpoints and Streamlit demo
6. 🔲 **Integration** — End-to-end tests and final polish


## License

MIT
