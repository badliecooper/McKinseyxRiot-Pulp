"""Tool registry for RIOT RADAR AI Copilot & Deterministic Orchestration.

Exposes standardized, deterministic tool functions called by both the LangGraph
pipeline and optional LLM tool-calling loops.
All outputs are grounded in actual service calculations.
"""

from typing import Dict, List, Optional, Any
import pandas as pd

from services.demand_service import DemandService
from services.distribution_service import DistributionService
from services.inventory_service import InventoryService
from services.risk_service import RiskService
from services.scenario_service import ScenarioService
from services.loss_attribution import (
    get_loss_categories,
    redistribute_root_causes,
    calculate_root_cause_exposures,
)
from graph.detection_pipeline import run_detection_pipeline
from graph.approval_pipeline import process_approval_decision
import approval

# Service Singletons
_demand_svc = DemandService()
_dist_svc = DistributionService()
_inv_svc = InventoryService()
_risk_svc = RiskService()
_scenario_svc = ScenarioService()


def scan_demand(sku_id: Optional[str] = None, depot_id: Optional[str] = None) -> Dict[str, Any]:
    """Scan demand signals, detect stockout censoring, and compute demand uplift."""
    s_id = sku_id if sku_id else "PR-DP"
    d_id = depot_id if depot_id else "Depot-West-01"
    return _demand_svc.detect_and_correct_censored_demand(s_id, d_id)


def find_surplus_and_shortage(sku_id: str) -> Dict[str, Any]:
    """Identify regional shortage and surplus depots for a given SKU based on the 21-day target."""
    grid_df = _dist_svc.get_45_sku_depot_grid()
    sku_sub = grid_df[grid_df["sku_id"] == sku_id]
    if sku_sub.empty:
        return {"sku_id": sku_id, "shortage_depots": [], "surplus_depots": []}

    shortages = sku_sub[sku_sub["days_of_cover"] < 14.0][
        ["depot_id", "depot_name", "days_of_cover", "allocation_gap", "projected_stockout_date"]
    ].to_dict(orient="records")

    surpluses = sku_sub[sku_sub["days_of_cover"] > 21.0][
        ["depot_id", "depot_name", "days_of_cover", "total_usable_stock", "remaining_shelf_life_days"]
    ].to_dict(orient="records")

    return {
        "sku_id": sku_id,
        "target_cover_days": 21,
        "shortage_depots": shortages,
        "surplus_depots": surpluses,
    }


def plan_rebalancing(sku_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Compute feasible inter-depot transfers protecting donor safety stock and checking shelf-life gates."""
    return _dist_svc.optimize_inter_depot_rebalancing(sku_id=sku_id)


def get_health_ribbon() -> Dict[str, Dict[str, str]]:
    """Fetch deterministic RAG status for Demand, Supply, Inventory, Distribution, Transportation."""
    return _risk_svc.evaluate_health_ribbon()


def get_national_kpis() -> Dict[str, Any]:
    """Fetch exactly the six national KPI metrics for the Control Tower."""
    return _risk_svc.get_national_kpis()


def get_sku_depot_grid() -> pd.DataFrame:
    """Fetch the full 45 SKU–Depot operational grain with all 22 required derived fields."""
    return _dist_svc.get_45_sku_depot_grid()


def simulate_passionfruit_disruption(
    closure_weeks: int = 3,
    starting_cover_days: int = 14,
    strategy: str = "CONTRIBUTION_OPTIMIZED",
    air_freight: bool = False,
) -> Dict[str, Any]:
    """Simulate passionfruit pulp depletion under highway closure with deterministic recipe rationing."""
    return _scenario_svc.simulate_passionfruit_disruption(
        closure_weeks=closure_weeks,
        starting_cover_days=starting_cover_days,
        rationing_strategy=strategy,
        air_freight_trigger=air_freight,
    )


def get_loss_attribution() -> Dict[str, Any]:
    """Retrieve non-overlapping historical loss categories and break-even recovery hurdle."""
    return get_loss_categories()


def run_pipeline(sku_id: Optional[str] = None, depot_id: Optional[str] = None) -> Dict[str, Any]:
    """Run the 6-node LangGraph detection and recommendation pipeline."""
    return run_detection_pipeline(target_sku_id=sku_id, target_depot_id=depot_id)


def submit_approval(
    recommendation_id: str,
    decision: str,
    approver_id: str = "Central-Planner",
    modified_quantity: Optional[int] = None,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    """Submit human approval decision (APPROVE, MODIFY, REJECT) to LangGraph approval workflow."""
    return approval.decide(
        recommendation_id=recommendation_id,
        decision=decision,
        approver_id=approver_id,
        modified_quantity_bottles=modified_quantity,
        notes=notes,
    )


def get_allocation_alignment() -> Dict[str, Any]:
    """Retrieve Allocation-vs-Demand Alignment Index comparing historical vs demand-driven allocations."""
    return _dist_svc.get_allocation_alignment_report()


def get_forecast_accuracy_breakdown(vintage_id: str = "VINTAGE-2026-W18") -> Dict[str, Any]:
    """Retrieve two-panel forecast metrics: National aggregate WAPE & Bias vs SKU-Depot local errors."""
    return _demand_svc.get_national_vs_local_forecast_metrics(vintage_id=vintage_id)


def get_causal_cascade() -> Dict[str, Any]:
    """Retrieve 6-stage cause-and-effect cascade indicators for the supply chain feedback loop."""
    return _scenario_svc.get_causal_cascade_metrics()


def get_pulp_build_timeline(
    starting_cover_days: int = 14,
    target_cover_days: int = 24,
    weekly_buffer_build_kg: float = 18000.0,
    holding_cost_rate: Optional[float] = 12.50,
) -> Dict[str, Any]:
    """Retrieve pre-summer passionfruit pulp buffer build timeline and financial comparison."""
    return _scenario_svc.get_pre_summer_pulp_build_timeline(
        starting_cover_days=starting_cover_days,
        target_cover_days=target_cover_days,
        weekly_buffer_build_kg=weekly_buffer_build_kg,
        holding_cost_inr_per_kg_month=holding_cost_rate,
    )
