# RIOT RADAR — Architecture Specification (React + FastAPI + LangGraph)

## 1. System Overview
RIOT RADAR is an institutional supply-chain control tower built for Pulp Riot Juice Co. to eliminate information asymmetry, recover stock-out censored latent demand, optimize inter-depot inventory rebalancing, and orchestrate human-governed operational actions.

```
       [ REACT 19 + TYPESCRIPT + VITE ENTERPRISE UI ]
(Control Tower | Depot Explorer | Scenario Replay | AI Copilot)
                              |
                              | REST API (JSON / HTTP)
                              v
                  [ FASTAPI BACKEND (api/main.py) ]
     (CORS enabled for localhost:5173, Pydantic validation)
                              |
        +---------------------+---------------------+
        |                                           |
        v                                           v
[ TOOLS & DETERMINISTIC SERVICES ]      [ LANGGRAPH STATEGRAPHS ]
- demand_service.py                     - Detection: 6-node StateGraph
- inventory_service.py                  - Approval: 3-node StateGraph
- distribution_service.py                           |
- scenario_service.py                               |
- loss_attribution.py                               |
- risk_service.py                                   |
- weekly_report.py (ReportLab PDF)                  |
        |                                           |
        +---------------------+---------------------+
                              |
                              v
                [ CSV PERSISTENCE (services/csv_store.py) ]
    (13 Canonical CSV tables: depots, products, demand_history, inventory,
     inbound_shipments, supplier_status, forecast_snapshots, recommendations,
     approvals, stockout_reports, audit_log, workflow_state, alarms)
```

## 2. Key Architecture Tenets
1. **React + TypeScript + Vite Control Tower:**
   - Dark slate institutional aesthetic (`#0b0f19` background, `#0f172a` cards, `#334155` borders).
   - Zero decorative emojis; strict semantic status badges (`[CRITICAL]`, `[WARN]`, `[OK]`, `[PENDING APPROVAL]`).
   - Tabular numerals for monetary amounts, bottle counts, and percentages.
   - TanStack Query for cache invalidation upon human decision approvals.
2. **FastAPI Authorization & Validation:**
   - Pydantic models for strict type checking on inputs and outputs.
   - Route modules: `/control-tower`, `/depot-explorer`, `/scenarios`, `/alarms`, `/copilot`, `/reports`.
   - Authoritative backend: all demand, inventory, transfer, and financial calculations executed in Python services.
3. **CSV-Only Persistence (`services/csv_store.py`):**
   - Strictly zero SQL, SQLite, SQLAlchemy, or ORM dependencies.
   - Atomic replacement via `tempfile.NamedTemporaryFile` and `os.replace`.
   - Single-concurrency thread-locked storage with schema verification.
4. **Two-Phase LangGraph Governance:**
   - **Detection Pipeline (6 nodes):**
     `ingest_signal` -> `detect_anomaly` -> `diagnose_risk` -> `forecast_demand` -> `evaluate_allocation` -> `generate_recommendation`.
     Emits tickets in `PENDING` state.
   - **Approval Pipeline (3 nodes):**
     `human_approval` -> `record_decision` -> `summarize_result`.
     Enforces that the AI agent only proposes; only human decision controls can commit actions.
     Prevents duplicate approvals and logs every event to `approvals.csv` and `audit_log.csv`.
5. **Non-Overlapping Financial Integrity:**
   - Stock-Out Lost Revenue: ₹46.08 Cr.
   - Foregone Contribution Margin (32%): ₹14.75 Cr (derived, not summed with revenue).
   - Bottom-Line Exposure: ₹23.95 Cr (₹14.75 Cr contribution + ₹6.00 Cr write-offs + ₹3.20 Cr air freight).
   - Year-1 Budget Guardrail: ₹2.50 Cr (10.4% hurdle rate).
