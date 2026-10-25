---
name: riot-radar-builder
description: Use when building or changing the Riot Radar / Pulp Riot control tower code (tools, engines, agent, Streamlit pages). Keeps calculations out of the UI, requires tests to actually run, and protects the human-approval rule.
---
# Riot Radar builder rules

1. Reuse the existing code (tools.py, agent.py, approval.py, data_gen.py). Read it before changing it. Do not rebuild working functions.
2. Deep modules are Demand and Distribution. Supply, Inventory and Transportation stay high-level.
3. Dependency direction: UI -> tools/engines -> data. No Streamlit imports in engines. No calculations inside UI code.
4. Every number shown in the UI must come from a tool function. No hardcoded outputs.
5. Approval: the agent may only request. Only `approval.decide()` records a decision, called from a human-facing control. Never mark anything as executed.
6. Build one vertical slice first: signal -> detect -> recommend -> approve -> log. Then extend.
7. Run the code. After each change run `python agent.py --replay` and the tests. Never write that a test passed unless it ran. Report failures as they are.
8. Label demonstration data on every screen: "SYNTHETIC DEMONSTRATION DATA".
9. Pages: Control Tower (depot map), Depot Explorer (one page, depot selector), Scenario Replay, AI Copilot. Cut extra pages before cutting correctness.
10. Keep the app working with no API key (deterministic brief) and make the Claude tool-calling loop the main path when a key exists.
