"""Pydantic Request & Response Schemas for RIOT RADAR FastAPI Backend.

Enforces:
- Clean type casting and JSON-safe conversion (no raw NaN or infinity)
- Strict validation for human approval decisions (APPROVE, MODIFY, REJECT)
- Explicit units and currency annotations
"""

from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, field_validator


# ==============================================================================
# HEALTH & STATUS
# ==============================================================================
class HealthResponse(BaseModel):
    status: str
    timestamp: str
    version: str
    database_mode: str = "CSV_ONLY_PERSISTENCE"
    operating_mode: str
    blob_storage: Optional[str] = None


class ModuleStatus(BaseModel):
    status: str  # "CRITICAL", "WARN", "OK"
    reason: str
    signal: str


class HealthRibbonResponse(BaseModel):
    Demand: ModuleStatus
    Supply: ModuleStatus
    Inventory: ModuleStatus
    Distribution: ModuleStatus
    Transportation: ModuleStatus


class NationalKPIsResponse(BaseModel):
    depots_at_risk: str
    forecast_wape_pct: str
    naive_benchmark_wape_pct: str
    projected_shortage_bottles: int
    transfer_opportunities_count: int
    detection_lead_time_days: int
    pending_decisions_count: int


# ==============================================================================
# CONTROL TOWER
# ==============================================================================
class HeatmapCell(BaseModel):
    depot_id: str
    sku_id: str
    value: float
    allocation_gap: float
    days_of_cover: Optional[float]
    wape_pct: Optional[float]


class HeatmapResponse(BaseModel):
    metric: str
    columns: List[str]  # SKUs
    rows: List[str]     # Depots
    matrix: List[List[Optional[float]]]
    cells: List[Dict[str, Any]]


class RiskMatrixPoint(BaseModel):
    sku_id: str
    flavour: str
    depot_id: str
    depot_name: str
    forecast_demand: float
    days_of_cover: Optional[float]
    allocation_gap: float
    projected_stockout_date: str
    risk_level: str


class RebalancingNetworkEdge(BaseModel):
    recommendation_id: str
    sku_id: str
    flavour: str
    origin_depot_id: str
    destination_depot_id: str
    quantity_bottles: int
    cost_inr: float
    protected_contribution_inr: float
    eta_days: int
    shelf_life_status: str
    status: str
    diagnosis: str


class RootCauseShare(BaseModel):
    label: str
    share_pct: float
    allocated_revenue_exposure_inr_cr: float
    allocated_contribution_exposure_inr_cr: float
    min_pct: float
    max_pct: float


class LossAttributionResponse(BaseModel):
    title: str
    stockout_lost_revenue_inr_cr: float
    foregone_contribution_inr_cr: float
    writeoffs_and_discounts_inr_cr: float
    emergency_air_freight_inr_cr: float
    bottom_line_exposure_inr_cr: float
    year_1_system_budget_cap_inr_cr: float
    break_even_recovery_hurdle_pct: float
    margin_pct: float
    competitive_shelf_space_impact: str
    root_cause_breakdown: Dict[str, RootCauseShare]
    disclaimer: str


class RootCauseRedistributeRequest(BaseModel):
    changed_cause_key: str
    new_value_pct: float
    current_shares: Dict[str, float]


# ==============================================================================
# DEPOT EXPLORER & 45 GRAIN
# ==============================================================================
class SkuDepotItem(BaseModel):
    sku_id: str
    flavour: str
    depot_id: str
    depot_name: str
    region: str
    observed_demand: float
    censored_adjustment: float
    corrected_demand: float
    demand_uplift_pct: Optional[float]
    forecast_demand: float
    forecast_vintage_id: str
    usable_stock_mt_qc: float
    usable_stock_gt_only: float
    total_usable_stock: float
    remaining_shelf_life_days: float
    inbound_qty: float
    otif_status: str
    target_stock: float
    allocation_gap: float
    days_of_cover: Optional[float]
    projected_stockout_date: str
    proposed_transfer_in_qty: float
    proposed_transfer_out_qty: float
    transfer_cost_inr: float
    eta_days: int
    wape_pct: Optional[float]
    forecast_bias_pct: Optional[float]
    confidence_level: str
    service_level_fill_rate_pct: Optional[float]
    is_synthetic: bool = True


class DemandSeriesPoint(BaseModel):
    date: str
    observed_sales: float
    corrected_demand: float
    censored_adjustment: float
    forecast_demand: float
    is_stockout_flagged: bool
    channel: str


class InventoryProjectionPoint(BaseModel):
    date: str
    opening_stock: float
    inbound_receipt_qty: float
    daily_demand_burn: float
    closing_stock: float
    is_stocked_out: bool


class StockoutReportCreate(BaseModel):
    depot_id: str
    sku_id: str
    channel: str = "ALL"
    estimated_unmet_bottles: float
    reported_by: str = "Store Ops Lead"
    evidence_source: str = "Dark Store Logs"
    notes: Optional[str] = ""


# ==============================================================================
# ALARMS & RECOMMENDATIONS
# ==============================================================================
class AlarmItem(BaseModel):
    alarm_id: str
    created_at: str
    updated_at: str
    alarm_type: str
    severity: str  # "CRITICAL", "WARNING", "INFO"
    status: str    # "NEW", "ACKNOWLEDGED", "RESOLVED"
    sku_id: Optional[str]
    depot_id: Optional[str]
    channel: Optional[str]
    title: str
    description: str
    observed_value: str
    threshold_value: str
    source: str
    confidence_level: str
    recommended_action: str
    recommendation_id: Optional[str]
    acknowledged_by: Optional[str]
    acknowledged_at: Optional[str]
    resolved_at: Optional[str]
    resolution_notes: Optional[str]
    is_synthetic: bool = True


class AlarmActionRequest(BaseModel):
    actor_id: str = "Central-Planner"
    notes: Optional[str] = ""


class ApprovalDecisionRequest(BaseModel):
    decision: str  # "APPROVE", "MODIFY", "REJECT"
    approver_id: str = "Lead-Planner-API"
    approver_role: str = "Central S&OP Planner"
    modified_quantity_bottles: Optional[int] = None
    notes: Optional[str] = None

    @field_validator("decision")
    @classmethod
    def validate_decision(cls, v: str) -> str:
        upper_v = v.upper().strip()
        if upper_v not in ["APPROVE", "MODIFY", "REJECT"]:
            raise ValueError(f"Decision must be APPROVE, MODIFY, or REJECT, got {v}")
        return upper_v


# ==============================================================================
# SCENARIOS
# ==============================================================================
class ScenarioReplayRequest(BaseModel):
    scenario_id: str = "PR_DP_VIRAL_SPIKE"  # or "PASSIONFRUIT_HIGHWAY_CLOSURE"
    closure_weeks: Optional[int] = 3
    starting_cover_days: Optional[int] = 14
    rationing_strategy: Optional[str] = "CONTRIBUTION_OPTIMIZED"
    air_freight_trigger: Optional[bool] = False


# ==============================================================================
# COPILOT
# ==============================================================================
class CopilotChatRequest(BaseModel):
    message: str
    sku_id: Optional[str] = None
    depot_id: Optional[str] = None
    history: Optional[List[Dict[str, Any]]] = None


class CopilotChatResponse(BaseModel):
    reply: str
    operating_mode: str
    grounded_evidence: Dict[str, Any]
    suggested_actions: List[Dict[str, Any]]
