"""
copilot.agents — LangGraph-based agent implementations.

This package contains the multi-agent system that processes flight disruption
claims. Each agent is a specialized node in a LangGraph state graph.

LEARN: In a multi-agent system, each agent has a specific role and capability.
Rather than building one monolithic LLM chain that tries to do everything,
we split the work into focused agents that each do one thing well:
  - Intake agent: free text → structured data (FlightDisruption)
  - Eligibility agent: structured data → rules engine → explanation
  - Drafter agent: structured data + eligibility → claim letter
  - Predictor agent: optional trained model → labelled score or availability warning
  - Supervisor: routes between agents based on what's needed next

Implemented in Phase 4. The intake extractor is provider-backed; the supervisor,
eligibility explanations, and factual draft template are deliberately deterministic.
"""
