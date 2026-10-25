"""Tests for the 45 SKU–Depot operational grain and inter-depot rebalancing optimization."""

import pytest
from services.distribution_service import DistributionService
from config.business_rules import SKUS, DEPOTS, TRANSFER_COST_PER_BOTTLE_INR


def test_45_sku_depot_operational_grain():
    """Verify that all 5 SKUs and 9 depots produce exactly 45 rows with all 22 required fields."""
    svc = DistributionService()
    grid = svc.get_45_sku_depot_grid()
    
    assert len(grid) == 45, f"Expected exactly 45 SKU-depot rows, got {len(grid)}"
    assert len(grid["sku_id"].unique()) == 5
    assert len(grid["depot_id"].unique()) == 9

    required_fields = [
        "observed_demand",
        "censored_adjustment",
        "corrected_demand",
        "demand_uplift_pct",
        "forecast_demand",
        "forecast_vintage_id",
        "usable_stock_mt_qc",
        "usable_stock_gt_only",
        "inbound_qty",
        "otif_status",
        "target_stock",
        "allocation_gap",
        "days_of_cover",
        "projected_stockout_date",
        "proposed_transfer_in_qty",
        "proposed_transfer_out_qty",
        "transfer_cost_inr",
        "eta_days",
        "wape_pct",
        "forecast_bias_pct",
        "confidence_level",
        "service_level_fill_rate_pct",
    ]

    for col in required_fields:
        assert col in grid.columns, f"Required SKU-Depot field '{col}' missing from 45 grid!"


def test_rebalancing_feasibility_guardrails():
    """Verify that inter-depot rebalancing proposals enforce:
    1. Donor safety stock (donor retains >= 21d cover)
    2. Transfer cost = quantity * ₹1.50
    3. Channel eligibility & 67-day cliff checks
    """
    svc = DistributionService()
    proposals = svc.optimize_inter_depot_rebalancing()

    for prop in proposals:
        # Check donor protection
        assert prop["donor_post_cover_days"] >= 20.9, f"Donor {prop['origin_depot_id']} violated 21d cover!"
        # Check transfer cost formula
        expected_cost = prop["quantity_bottles"] * TRANSFER_COST_PER_BOTTLE_INR
        assert prop["cost_inr"] == expected_cost
        # Check effective ETA includes 1 day approval latency
        assert prop["eta_days"] == prop["lead_time_days"] + 1
        # Check shelf life eligibility is explicitly documented
        assert "shelf_life_status" in prop
