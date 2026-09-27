"""
copilot.graph — LangGraph workflow definition.

This package defines the state graph that wires agents together. The graph
is the "control flow" of the multi-agent system: it decides which agent
runs next based on the current state.

LEARN: LangGraph models agent workflows as directed graphs where:
  - Nodes are functions (agents) that transform the state
  - Edges define the flow between nodes
  - Conditional edges let you branch based on state values
Think of it as a flowchart Python executes. Only free-text intake calls an LLM;
the supervisor, rules, prediction tool, and factual drafting template are code.

Implemented in Phase 4.
"""
