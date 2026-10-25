export interface ModuleStatus {
  status: "CRITICAL" | "WARN" | "OK";
  reason: string;
  signal: string;
}

export interface HealthRibbon {
  Demand: ModuleStatus;
  Supply: ModuleStatus;
  Inventory: ModuleStatus;
  Distribution: ModuleStatus;
  Transportation: ModuleStatus;
}

export interface NationalKPIs {
  depots_at_risk: string;
  forecast_wape_pct: string;
  naive_benchmark_wape_pct: string;
  projected_shortage_bottles: number;
  transfer_opportunities_count: number;
  detection_lead_time_days: number;
  pending_decisions_count: number;
}

export interface HeatmapCell {
  depot_id: string;
  sku_id: string;
  flavour: string;
  value: number | null;
  allocation_gap: number;
  days_of_cover: number | null;
  wape_pct: number | null;
  corrected_demand: number;
  total_usable_stock: number;
}

export interface HeatmapResponse {
  metric: string;
  columns: string[];
  rows: string[];
  matrix: (number | null)[][];
  cells: HeatmapCell[];
}

export interface RiskMatrixPoint {
  sku_id: string;
  flavour: string;
  depot_id: string;
  depot_name: string;
  forecast_demand: number;
  days_of_cover: number | null;
  allocation_gap: number;
  projected_stockout_date: string;
  risk_level: "CRITICAL" | "WARNING" | "SURPLUS" | "HEALTHY";
}

export interface RiskMatrixResponse {
  points: RiskMatrixPoint[];
  thresholds: {
    critical_cover_days: number;
    warning_cover_days: number;
    target_cover_days: number;
    high_demand_threshold: number;
  };
}

export interface RebalancingProposal {
  recommendation_id: string;
  created_at: string;
  priority: "P1" | "P2";
  module: string;
  sku_id: string;
  flavour: string;
  origin_depot_id: string;
  destination_depot_id: string;
  action_type: string;
  quantity_bottles: number;
  cost_inr: number;
  protected_contribution_inr: number;
  lead_time_days: number;
  eta_days: number;
  shelf_life_status: string;
  channel_eligibility: string;
  donor_cover_before_days: number;
  donor_post_cover_days: number;
  destination_cover_before_days: number;
  destination_post_cover_days: number;
  shortage_reduction_bottles: number;
  status: "PENDING" | "APPROVED" | "MODIFIED" | "REJECTED";
  confidence_level: string;
  diagnosis: string;
  selection_rationale?: string;
  rejected_alternatives?: string;
  candidates_evaluated?: any[];
  is_synthetic: boolean;
}

export interface RootCauseShare {
  label: string;
  share_pct: number;
  allocated_revenue_exposure_inr_cr: number;
  allocated_contribution_exposure_inr_cr: number;
  min_pct: number;
  max_pct: number;
}

export interface LossAttributionData {
  title: string;
  stockout_lost_revenue_inr_cr: number;
  foregone_contribution_inr_cr: number;
  writeoffs_and_discounts_inr_cr: number;
  emergency_air_freight_inr_cr: number;
  bottom_line_exposure_inr_cr: number;
  year_1_system_budget_cap_inr_cr: number;
  break_even_recovery_hurdle_pct: number;
  margin_pct: number;
  competitive_shelf_space_impact: string;
  root_cause_breakdown: Record<string, RootCauseShare>;
  disclaimer: string;
  shares_sum_pct?: number;
}

export interface AlarmItem {
  alarm_id: string;
  created_at: string;
  updated_at: string;
  alarm_type: string;
  severity: "CRITICAL" | "WARNING" | "INFO";
  status: "NEW" | "ACKNOWLEDGED" | "RESOLVED";
  sku_id?: string;
  depot_id?: string;
  channel?: string;
  title: string;
  description: string;
  observed_value: string;
  threshold_value: string;
  source: string;
  confidence_level: string;
  recommended_action: string;
  recommendation_id?: string;
  acknowledged_by?: string;
  acknowledged_at?: string;
  resolved_at?: string;
  resolution_notes?: string;
  is_read?: boolean;
  is_synthetic: boolean;
}

export interface SkuDepotItem {
  sku_id: string;
  flavour: string;
  depot_id: string;
  depot_name: string;
  region: string;
  observed_demand: number;
  censored_adjustment: number;
  corrected_demand: number;
  demand_uplift_pct: number | null;
  forecast_demand: number;
  forecast_vintage_id: string;
  usable_stock_mt_qc: number;
  usable_stock_gt_only: number;
  total_usable_stock: number;
  remaining_shelf_life_days: number;
  inbound_qty: number;
  otif_status: string;
  target_stock: number;
  allocation_gap: number;
  days_of_cover: number | null;
  projected_stockout_date: string;
  proposed_transfer_in_qty: number;
  proposed_transfer_out_qty: number;
  transfer_cost_inr: number;
  eta_days: number;
  wape_pct: number | null;
  forecast_bias_pct: number | null;
  confidence_level: string;
  service_level_fill_rate_pct: number | null;
  is_synthetic: boolean;
}

export interface DemandSeriesPoint {
  date: string;
  observed_sales: number;
  corrected_demand: number;
  censored_adjustment: number;
  forecast_demand: number;
  is_stockout_flagged: boolean;
  channel: string;
}

export interface InventoryProjectionPoint {
  date: string;
  opening_stock: number;
  inbound_receipt_qty: number;
  transfer_in_qty?: number;
  available_usable_stock?: number;
  daily_demand_burn: number;
  fulfilled_demand?: number;
  unmet_demand?: number;
  closing_stock: number;
  days_of_cover?: number;
  is_stocked_out: boolean;
  intervention_note?: string;
  data_type?: string;
}

export interface ScenarioLedgerRow {
  day: number;
  date: string;
  opening_stock: number;
  inbound_receipt_qty: number;
  transfer_in_qty: number;
  available_usable_stock: number;
  daily_demand: number;
  fulfilled_demand: number;
  unmet_demand: number;
  closing_stock: number;
  days_of_cover: number;
  is_stocked_out: boolean;
  intervention_note: string;
  source_record: string;
  data_type: "Observed" | "Calculated" | "Simulated" | string;
}

export interface ScenarioCalculationLedger {
  evaluation_start_date: string;
  evaluation_horizon_days: number;
  historical_ledger: ScenarioLedgerRow[];
  radar_ledger: ScenarioLedgerRow[];
  summary: {
    opening_stock_bottles: number;
    historical_projected_stockout_date?: string | null;
    radar_projected_stockout_date?: string | null;
    historical_total_unmet_demand_bottles: number;
    radar_total_unmet_demand_bottles: number;
    stockout_prevented_bottles: number;
    protected_contribution_inr: number;
    mitigation_cost_inr: number;
    rebalancing_coverage_pct: number;
  };
}

export interface ScenarioData {
  scenario_id: string;
  title: string;
  kpis: {
    detection_advantage_days: number;
    shortage_reduction_bottles: number;
    rebalancing_coverage_pct: number;
    net_mitigation_cost_inr: number;
    protected_contribution_inr: number;
  };
  timeline_events: {
    first_signal_date: string;
    agent_flag_date: string;
    human_approval_date: string;
    transfer_arrival_date: string;
    historical_planner_notice_date: string;
  };
  waterfall: {
    label: string;
    value: number;
    type: "absolute" | "relative" | "total";
    annotation: string;
  }[];
  daily_cover_comparison: {
    day: number;
    date?: string;
    historical_cover_days: number;
    radar_cover_days: number;
  }[];
  calculation_ledger?: ScenarioCalculationLedger;
  supply_constraints_note: string;
}

export interface DepotAlignmentBreakdown {
  depot_id: string;
  allocated_qty: number;
  demand_qty: number;
  allocation_share_pct: number;
  demand_share_pct: number;
  mismatch_contribution_pct: number;
}

export interface SkuAlignmentIndex {
  sku_id: string;
  flavour: string;
  historical_mix_index_pct: number;
  current_allocation_index_pct: number;
  post_intervention_index_pct: number;
  improvement_pct: number;
  historical_depot_breakdown: DepotAlignmentBreakdown[];
  current_depot_breakdown: DepotAlignmentBreakdown[];
  post_intervention_depot_breakdown: DepotAlignmentBreakdown[];
}

export interface AllocationAlignmentReport {
  overall_historical_mix_index_pct?: number;
  overall_post_intervention_index_pct?: number;
  overall_improvement_pct?: number;
  sku_alignment_indices: SkuAlignmentIndex[];
  metric_name: string;
  metric_definition: string;
  data_honesty_note: string;
}

export interface ForecastAccuracyComparison {
  vintage_id: string;
  evaluation_period: string;
  sku_depots_count: number;
  national_panel: {
    wape_pct: number;
    bias_pct: number;
    bias_direction: string;
    total_forecast_bottles: number;
    total_actual_bottles: number;
  };
  sku_depot_panel: {
    wape_pct: number;
    mean_absolute_bias_pct: number;
    signed_mean_bias_pct: number;
    cancelling_error_gap_pct: number;
  };
  sku_breakdown: {
    sku_id: string;
    flavour: string;
    national_wape_pct: number;
    national_bias_pct: number;
    mean_abs_depot_bias_pct: number;
    cancelling_gap_pct: number;
  }[];
  aggregation_fallacy_note: string;
  data_honesty_note: string;
}

export interface CausalCascadeNode {
  id: string;
  step_number: number;
  title: string;
  short_desc: string;
  model_metric_label: string;
  model_metric_value: string;
  status: "MITIGATED" | "ACTIVE_RISK" | "NEUTRAL";
  supporting_calculation: string;
  affected_sku_depots: string[];
  evidence: string;
  mitigation_lever: string;
}

export interface CausalCascadeData {
  title: string;
  nodes: CausalCascadeNode[];
  disclaimer: string;
}

export interface PulpBuildTimelineData {
  case_facts: {
    frozen_pulp_shelf_life_months: number;
    frozen_pulp_shelf_life_days: number;
    expected_highway_closure_duration_days: number;
    expected_highway_closure_weeks: number;
    normal_road_transit_days: number;
    starting_cover_days_case_fact: number;
    historical_emergency_air_freight_inr_cr: number;
  };
  planning_parameters: {
    starting_cover_days: number;
    target_buffer_cover_days: number;
    normal_daily_consumption_kg: number;
    starting_pulp_stock_kg: number;
    target_pulp_stock_kg: number;
    required_additional_buffer_kg: number;
    weekly_buffer_build_kg: number;
    holding_cost_rate_inr_per_kg_month: number | null;
  };
  financial_comparison: {
    estimated_buffer_holding_cost_inr_cr: number | null;
    historical_air_freight_reference_inr_cr: number;
    net_avoided_exposure_inr_cr: number;
    is_holding_cost_available: boolean;
  };
  weekly_timeline: {
    week_number: number;
    week_label: string;
    projected_cover_days: number;
    pulp_stock_kg: number;
    planned_weekly_procurement_kg: number;
    target_cover_reference_days: number;
    highway_closure_reference_days: number;
    is_target_achieved: boolean;
  }[];
  data_honesty_note: string;
}

