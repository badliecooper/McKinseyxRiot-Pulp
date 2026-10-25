"""Scenario Replay API endpoints for RIOT RADAR."""

from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException

import tools
from api.schemas import ScenarioReplayRequest

router = APIRouter(prefix="/scenarios", tags=["Scenarios"])


@router.get("")
def get_scenarios():
    """Retrieve available calibrated supply chain disruption scenarios."""
    return {
        "scenarios": [
            {
                "scenario_id": "PR_DP_VIRAL_SPIKE",
                "title": "Dragon Passion demand spike",
                "description": "Viral influencer video triggers 4.1x velocity uplift in Mumbai/Delhi dark stores over 14 days.",
                "primary_sku": "PR-DP",
                "default_detection_advantage_days": 17,
            },
            {
                "scenario_id": "PASSIONFRUIT_HIGHWAY_CLOSURE",
                "title": "Passionfruit road closure",
                "description": "Road disruption severs single-source raw passionfruit pulp route. Starting plant cover is 14 days.",
                "primary_sku": "PR-PP",
                "default_detection_advantage_days": 13,
            },
        ]
    }


@router.post("/replay")
def post_scenario_replay(req: ScenarioReplayRequest):
    """Run deterministic scenario replay comparing Historical Baseline vs RIOT RADAR."""
    scenario_id = req.scenario_id or "PR_DP_VIRAL_SPIKE"
    timeline_meta = tools._scenario_svc.get_scenario_timeline_comparison(scenario_id)

    closure_w = req.closure_weeks or 3
    starting_c = req.starting_cover_days or 14
    strat = req.rationing_strategy or "CONTRIBUTION_OPTIMIZED"
    air = req.air_freight_trigger or False

    ledger_result = tools._scenario_svc.generate_deterministic_scenario_ledger(
        scenario_id=scenario_id,
        closure_weeks=closure_w,
        starting_cover_days=starting_c,
        rationing_strategy=strat,
        air_freight_trigger=air,
    )

    if scenario_id == "PR_DP_VIRAL_SPIKE":
        waterfall_steps = [
            {"label": "Baseline Projected Shortage", "value": 102000, "type": "absolute", "annotation": "102,000 btls"},
            {"label": "Inter-Depot Transfers", "value": -58000, "type": "relative", "annotation": "-58,000 btls (@ ₹1.50)"},
            {"label": "Plant Overtime Allocation", "value": -20000, "type": "relative", "annotation": "-20,000 btls"},
            {"label": "Residual Unmet Demand", "value": 24000, "type": "total", "annotation": "24,000 btls"},
        ]
        mitigation_cost_inr = ledger_result["summary"]["mitigation_cost_inr"]
        rebalancing_coverage_pct = ledger_result["summary"]["rebalancing_coverage_pct"]
    else:
        waterfall_steps = [
            {"label": "Baseline Pulp Deficit", "value": 125000, "type": "absolute", "annotation": "125,000 btls eq"},
            {"label": "Deterministic Rationing (Protect PR-DP)", "value": -45000, "type": "relative", "annotation": "-45,000 btls (PR-PP -35%)"},
            {"label": "Emergency Air Freight Contingency", "value": -60000 if air else 0, "type": "relative", "annotation": "-60,000 btls (₹3.20 Cr)" if air else "0 btls"},
            {"label": "Residual Unmet Deficit", "value": 20000 if air else 80000, "type": "total", "annotation": "20,000 btls eq" if air else "80,000 btls eq"},
        ]
        mitigation_cost_inr = ledger_result["summary"]["mitigation_cost_inr"]
        rebalancing_coverage_pct = ledger_result["summary"]["rebalancing_coverage_pct"]

    return {
        "scenario_id": scenario_id,
        "title": timeline_meta["scenario_name"],
        "kpis": {
            "detection_advantage_days": timeline_meta["detection_advantage_days"],
            "shortage_reduction_bottles": timeline_meta["stockout_prevented_bottles"],
            "rebalancing_coverage_pct": rebalancing_coverage_pct,
            "net_mitigation_cost_inr": mitigation_cost_inr,
            "protected_contribution_inr": timeline_meta["protected_contribution_inr"],
        },
        "timeline_events": {
            "first_signal_date": timeline_meta["first_qc_signal_date"],
            "agent_flag_date": timeline_meta["agent_flag_date"],
            "human_approval_date": timeline_meta["human_approval_date"],
            "transfer_arrival_date": timeline_meta["transfer_arrival_date"],
            "historical_planner_notice_date": timeline_meta["historical_planner_notice_date"],
        },
        "waterfall": waterfall_steps,
        "daily_cover_comparison": ledger_result["daily_cover_comparison"],
        "calculation_ledger": {
            "evaluation_start_date": ledger_result["evaluation_start_date"],
            "evaluation_horizon_days": ledger_result["evaluation_horizon_days"],
            "historical_ledger": ledger_result["historical_ledger"],
            "radar_ledger": ledger_result["radar_ledger"],
            "summary": ledger_result["summary"],
        },
        "supply_constraints_note": (
            "SCM Constraint: Co-packer provides line bottling capacity (+25% premium, 14d notice) "
            "but CANNOT resolve raw pulp scarcity when Northeast road transit is blocked."
        ),
    }


@router.get("/causal-cascade")
def get_scenario_causal_cascade():
    """Retrieve live model-derived indicators across the 6-stage cause-and-effect cascade."""
    return tools.get_causal_cascade()


@router.get("/alignment-index")
def get_scenario_alignment_index():
    """Retrieve before-and-after Allocation-vs-Demand Alignment Index for scenario comparison."""
    return tools.get_allocation_alignment()

