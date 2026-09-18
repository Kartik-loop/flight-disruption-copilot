"""
copilot.rules — Deterministic compensation rules engines.

WHY THIS EXISTS:
The rules for EU261 and US DOT compensation are LAWS with specific, testable
conditions. An LLM should never decide whether someone gets €250 or €400 —
that's a deterministic lookup based on distance and disruption type.

LEARN: This is a critical architectural decision. We separate the system into:
  1. LLM tasks: understanding free text, extracting facts, explaining results
  2. Deterministic tasks: applying legal rules to structured facts
The LLM is good at (1) but unreliable at (2). By putting rules in plain Python
with unit tests, we get auditable, reproducible results. The LLM's job is
to feed clean data INTO the rules engine and explain the results OUT.

This package contains:
  - eu261.py: European regulation EC 261/2004
  - dot.py: US Department of Transportation rules
  - engine.py: Router that picks the right rules based on region
"""
