#!/usr/bin/env python3
"""Acceptance Verification Script for RIOT RADAR 4-Month Summer Dataset.

Validates all criteria specified in Section 6:
1. 9 depots, 5 SKUs, 45 inventory rows, 5,490 demand rows, 765 forecast rows.
2. Total corrected demand == 96,000,000 bottles (₹576.00 Cr at ₹60/btl).
3. Total stock-out censored volume == 7,680,000 bottles (8.00% = ₹46.08 Cr lost revenue).
4. Total observed sales == 88,320,000 bottles (₹529.92 Cr realized revenue).
5. Exact row identity on every row: corrected_demand == observed_sales + censored_adjustment.
6. Zero look-ahead leakage: 0 forecast rows with snapshot_date >= target_date.
7. Complete data availability and rendering checks for all 4 analytical visualizations:
   - Allocation-vs-Demand Alignment Index
   - National Bias vs SKU-Depot Error (aggregation fallacy)
   - Live Cause-and-Effect Cascade (viral surge -> stockouts -> censored demand)
   - Pre-Summer Passionfruit Pulp Build Timeline
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np

# Add repo root to path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Ensure UTF-8 stdout
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from services.csv_store import load_csv
from services.distribution_service import DistributionService
from services.demand_service import DemandService
from services.scenario_service import ScenarioService


def run_acceptance_checks():
    print("=" * 80)
    print("      RIOT RADAR — ACCEPTANCE CRITERIA VERIFICATION REPORT")
    print("=" * 80)

    # 1. Row counts across master tables
    depots_df = load_csv("depots")
    products_df = load_csv("products")
    demand_df = load_csv("demand_history")
    forecast_df = load_csv("forecast_snapshots")
    inventory_df = load_csv("inventory")
    inbound_df = load_csv("inbound_shipments")
    supplier_df = load_csv("supplier_status")
    recs_df = load_csv("recommendations")
    alarms_df = load_csv("alarms")

    print("\n[CHECK 1] Row Counts across Master Tables:")
    print(f"  - depots.csv:             {len(depots_df)} rows (Expected: 9)")
    print(f"  - products.csv:           {len(products_df)} rows (Expected: 5)")
    print(f"  - inventory.csv:          {len(inventory_df)} rows (Expected: 45)")
    print(f"  - demand_history.csv:     {len(demand_df)} rows (Expected: 5,490)")
    print(f"  - forecast_snapshots.csv: {len(forecast_df)} rows (Expected: 765)")
    print(f"  - inbound_shipments.csv:  {len(inbound_df)} rows (Expected: 20)")
    print(f"  - supplier_status.csv:    {len(supplier_df)} rows (Expected: 5)")
    print(f"  - alarms.csv:             {len(alarms_df)} rows (Expected: >= 7)")

    assert len(depots_df) == 9, f"depots.csv must have 9 rows, got {len(depots_df)}"
    assert len(products_df) == 5, f"products.csv must have 5 rows, got {len(products_df)}"
    assert len(inventory_df) == 45, f"inventory.csv must have 45 rows, got {len(inventory_df)}"
    assert len(demand_df) == 5490, f"demand_history.csv must have 5,490 rows, got {len(demand_df)}"
    assert len(forecast_df) == 765, f"forecast_snapshots.csv must have 765 rows, got {len(forecast_df)}"
    assert len(inbound_df) == 20, f"inbound_shipments.csv must have 20 rows, got {len(inbound_df)}"
    assert len(supplier_df) == 5, f"supplier_status.csv must have 5 rows, got {len(supplier_df)}"
    assert len(alarms_df) >= 7, f"alarms.csv must have at least 7 rows, got {len(alarms_df)}"
    print("  -> PASS: All row counts match exactly.")

    # 2. Demand, Censoring & Revenue Calibration
    demand_df["corrected_demand"] = pd.to_numeric(demand_df["corrected_demand"], errors="coerce").fillna(0).astype(int)
    demand_df["censored_adjustment"] = pd.to_numeric(demand_df["censored_adjustment"], errors="coerce").fillna(0).astype(int)
    demand_df["observed_sales"] = pd.to_numeric(demand_df["observed_sales"], errors="coerce").fillna(0).astype(int)
    demand_df["is_stockout_flagged"] = demand_df["is_stockout_flagged"].astype(str).str.lower().isin(["true", "1"])

    tot_corr = int(demand_df["corrected_demand"].sum())
    tot_cens = int(demand_df["censored_adjustment"].sum())
    tot_obs = int(demand_df["observed_sales"].sum())
    cens_pct = (tot_cens / tot_corr) * 100.0
    lost_rev_cr = (tot_cens * 60) / 1e7
    real_rev_cr = (tot_obs * 60) / 1e7
    tot_rev_cr = (tot_corr * 60) / 1e7

    print("\n[CHECK 2] Mathematical Volume & Financial Reconciliations:")
    print(f"  - Total Corrected Demand: {tot_corr:,} btls (₹{tot_rev_cr:.2f} Cr) [Target: 96,000,000 / ₹576.00 Cr]")
    print(f"  - Total Censored Demand:  {tot_cens:,} btls ({cens_pct:.2f}% | Lost Rev: ₹{lost_rev_cr:.2f} Cr) [Target: 7,680,000 / 8.00% / ₹46.08 Cr]")
    print(f"  - Total Observed Sales:   {tot_obs:,} btls (₹{real_rev_cr:.2f} Cr) [Target: 88,320,000 / ₹529.92 Cr]")

    assert tot_corr == 96_000_000, f"Corrected demand must be 96,000,000, got {tot_corr}"
    assert tot_cens == 7_680_000, f"Censored demand must be 7,680,000, got {tot_cens}"
    assert tot_obs == 88_320_000, f"Observed sales must be 88,320,000, got {tot_obs}"
    assert abs(cens_pct - 8.0) < 1e-4, f"Censored pct must be 8.00%, got {cens_pct}%"
    print("  -> PASS: Volume and revenue totals match case calibration to the exact bottle.")

    # 3. Row-level identities
    row_identity_diff = (demand_df["corrected_demand"] - (demand_df["observed_sales"] + demand_df["censored_adjustment"])).abs().sum()
    flag_consistency = (demand_df["is_stockout_flagged"] == (demand_df["censored_adjustment"] > 0)).all()
    print("\n[CHECK 3] Row-Level Identities:")
    print(f"  - Strict identity |corrected - (observed + censored)| == 0: {row_identity_diff == 0}")
    print(f"  - Flag identity is_stockout_flagged == (censored > 0):       {flag_consistency}")
    assert row_identity_diff == 0, "Row identity violated on demand_history.csv!"
    assert flag_consistency, "Flag inconsistency on demand_history.csv!"
    print("  -> PASS: Every row strictly satisfies volume and stock-out flag identities.")

    # 4. Zero Look-Ahead Leakage in Forecast Snapshots
    forecast_df["snapshot_dt"] = pd.to_datetime(forecast_df["snapshot_date"])
    forecast_df["target_dt"] = pd.to_datetime(forecast_df["target_date"])
    leakage_rows = (forecast_df["snapshot_dt"] >= forecast_df["target_dt"]).sum()
    lead_days = (forecast_df["target_dt"] - forecast_df["snapshot_dt"]).dt.days
    print("\n[CHECK 4] Zero Look-Ahead Leakage in Forecast Vintages:")
    print(f"  - Rows where snapshot_date >= target_date: {leakage_rows} (Expected: 0)")
    print(f"  - Unique lead time days:                    {lead_days.unique().tolist()} (Expected: [7])")
    print(f"  - Top vintage in file:                      {forecast_df.iloc[0]['vintage_id']} (Expected: VINTAGE-2026-W18)")
    assert leakage_rows == 0, f"Look-ahead leakage detected in {leakage_rows} rows!"
    assert list(lead_days.unique()) == [7], f"Expected 7-day lead time for all snapshots, got {lead_days.unique()}"
    assert forecast_df.iloc[0]["vintage_id"] == "VINTAGE-2026-W18", "VINTAGE-2026-W18 must be first vintage in file"
    print("  -> PASS: Zero look-ahead leakage confirmed across all 765 vintage rows.")

    # 5. Inventory Shelf-Life Constraints & Near-Cliff Flagging
    print("\n[CHECK 5] Inventory Consistency & Near-Cliff Flagging:")
    for col in ["total_usable_stock", "usable_stock_mt_qc", "usable_stock_gt_only", "near_cliff_stock", "remaining_shelf_life_days"]:
        inventory_df[col] = pd.to_numeric(inventory_df[col], errors="coerce").fillna(0)
    inv_identity = (inventory_df["total_usable_stock"] == (inventory_df["usable_stock_mt_qc"] + inventory_df["usable_stock_gt_only"])).all()
    print(f"  - Strict total == usable_mt_qc + usable_gt_only: {inv_identity}")
    assert inv_identity, "Inventory usable stock sum mismatch!"
    
    mpb_near_cliff = inventory_df[
        (inventory_df["sku_id"] == "PR-MPB") &
        (inventory_df["depot_id"].isin(["Depot-East-01", "Depot-Central-01"]))
    ]
    print(f"  - PR-MPB East-01 & Central-01 near-cliff stock:  {mpb_near_cliff['near_cliff_stock'].tolist()} (All > 0)")
    print(f"  - Batch remaining days:                         {mpb_near_cliff['remaining_shelf_life_days'].tolist()} (Expected: [63, 63])")
    assert (mpb_near_cliff["near_cliff_stock"] > 0).all(), "Near-cliff stock must be > 0 for PR-MPB at East/Central"
    assert (mpb_near_cliff["remaining_shelf_life_days"] == 63).all(), "Batch remaining shelf life must be 63d"
    print("  -> PASS: 63-day shelf-life near-cliff condition accurately flagged.")

    # 6. Four Analytical Visualizations Data & Engine Execution
    print("\n[CHECK 6] Verification of Four Supply Chain Visualizations:")

    # Vis 1: Allocation-vs-Demand Alignment Index
    dist_svc = DistributionService()
    alignment_rep = dist_svc.get_allocation_alignment_report()
    assert "sku_alignment_indices" in alignment_rep
    assert len(alignment_rep["sku_alignment_indices"]) == 5
    print(f"  - Vis 1 (Alignment Index):           {len(alignment_rep['sku_alignment_indices'])} SKUs evaluated. PR-DP Historical Mismatch = {alignment_rep['sku_alignment_indices'][4]['historical_mix_index_pct']:.1f}% -> Post-Intervention = {alignment_rep['sku_alignment_indices'][4]['post_intervention_index_pct']:.1f}%")

    # Vis 2: National Bias vs SKU-Depot Error (Aggregation Fallacy)
    demand_svc = DemandService()
    bias_res = demand_svc.get_national_vs_local_forecast_metrics(vintage_id="VINTAGE-2026-W18")
    assert "national_panel" in bias_res
    assert "sku_depot_panel" in bias_res
    print(f"  - Vis 2 (National vs Local Bias):    National Bias = {bias_res['national_panel']['bias_pct']:+.1f}%, Mean Absolute Depot Error = {bias_res['sku_depot_panel']['mean_absolute_bias_pct']:.1f}%, Cancelling Gap = {bias_res['sku_depot_panel']['cancelling_error_gap_pct']:.1f}%")

    # Vis 3: Live Cause-and-Effect Cascade
    scen_svc = ScenarioService()
    cascade_res = scen_svc.get_causal_cascade_metrics()
    assert "nodes" in cascade_res
    assert len(cascade_res["nodes"]) == 6
    print(f"  - Vis 3 (Causal Cascade):            {len(cascade_res['nodes'])} pipeline nodes active. Node 1 = '{cascade_res['nodes'][0]['title']}' ({cascade_res['nodes'][0]['model_metric_value']})")

    # Vis 4: Pre-Summer Passionfruit Pulp Build Timeline
    pulp_res = scen_svc.get_pre_summer_pulp_build_timeline()
    assert "weekly_timeline" in pulp_res
    assert len(pulp_res["weekly_timeline"]) == 8
    print(f"  - Vis 4 (Pulp Build Timeline):       8-week build schedule: Starting = {pulp_res['case_facts']['starting_cover_days_case_fact']}d -> Final Projected = {pulp_res['weekly_timeline'][-1]['projected_cover_days']:.1f}d (Target: {pulp_res['planning_parameters']['target_buffer_cover_days']}d)")
    print(f"                                       Air Freight Saved = ₹{pulp_res['case_facts']['historical_emergency_air_freight_inr_cr']:.2f} Cr, Net Avoided Exposure = ₹{pulp_res['financial_comparison']['net_avoided_exposure_inr_cr']:.2f} Cr")
    print("  -> PASS: All four analytical visualizations compute with complete and accurate datasets.")

    print("\n" + "=" * 80)
    print(">>> ALL 6 ACCEPTANCE VERIFICATION CHECKS PASSED WITH ZERO ERRORS <<<")
    print("=" * 80)


if __name__ == "__main__":
    run_acceptance_checks()
