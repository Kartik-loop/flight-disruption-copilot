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
"""

from copilot.rules.dot import evaluate_dot
from copilot.rules.engine import determine_applicable_region, evaluate_disruption_rules
from copilot.rules.eu261 import evaluate_eu261

__all__ = [
    "evaluate_disruption_rules",
    "evaluate_eu261",
    "evaluate_dot",
    "determine_applicable_region",
]
