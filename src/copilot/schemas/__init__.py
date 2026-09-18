"""
copilot.schemas — Pydantic models that define the data contracts of the system.

WHY THIS EXISTS:
Every agent in the system needs to agree on what a "flight disruption" looks like,
what an "eligibility result" contains, etc. Instead of passing around raw dicts
(which are error-prone), we define strict Pydantic models. This gives us:
  1. Automatic validation (wrong types → clear error messages)
  2. Serialization to/from JSON (for the API and LLM tool calls)
  3. Self-documenting code (the model IS the documentation)

LEARN: Pydantic is the de-facto standard for data validation in modern Python.
FastAPI uses it for request/response models, LangChain uses it for tool schemas,
and we use it as the shared language between all agents. Defining schemas in one
place prevents every agent from inventing its own ad-hoc format.
"""
