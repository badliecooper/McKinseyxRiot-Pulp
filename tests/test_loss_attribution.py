"""Tests for Loss Attribution and non-overlapping financial guardrails."""

import pytest
from services.loss_attribution import (
    get_loss_categories,
    redistribute_root_causes,
    calculate_root_cause_exposures,
)
from config.business_rules import (
    HISTORICAL_STOCKOUT_LOST_REVENUE_INR_CR,
    HISTORICAL_FOREGONE_CONTRIBUTION_INR_CR,
    HISTORICAL_WRITEOFFS_DISCOUNTS_INR_CR,
    HISTORICAL_AIR_FREIGHT_INR_CR,
    HISTORICAL_BOTTOM_LINE_EXPOSURE_INR_CR,
    YEAR_1_SYSTEM_BUDGET_CAP_INR_CR,
    BREAK_EVEN_RECOVERY_HURDLE_PCT,
)


def test_non_overlapping_loss_categories():
    """Verify that lost revenue and foregone contribution are kept strictly separate.
    
    Bottom-Line Exposure = Foregone Contribution + Write-offs + Emergency Air Freight
    ₹14.75 Cr + ₹6.00 Cr + ₹3.20 Cr = ₹23.95 Cr.
    """
    loss = get_loss_categories()
    assert loss["stockout_lost_revenue_inr_cr"] == 46.08
    assert loss["foregone_contribution_inr_cr"] == 14.75
    assert loss["writeoffs_and_discounts_inr_cr"] == 6.00
    assert loss["emergency_air_freight_inr_cr"] == 3.20

    # Ensure bottom line exposure equals the sum of the 3 bottom-line categories
    bottom_line_sum = round(
        loss["foregone_contribution_inr_cr"]
        + loss["writeoffs_and_discounts_inr_cr"]
        + loss["emergency_air_freight_inr_cr"],
        2,
    )
    assert bottom_line_sum == 23.95
    assert loss["bottom_line_exposure_inr_cr"] == 23.95

    # Hurdle check: 2.50 / 23.95 = 10.4%
    assert loss["break_even_recovery_hurdle_pct"] == 10.4


def test_root_cause_slider_redistribution():
    """Verify interactive root-cause redistribution:
    1. Sum always equals 100%.
    2. Respects configured min/max bounds:
       - Late demand: [30, 40]
       - Stale allocation: [35, 45]
       - Pulp disruption: [20, 30]
    """
    initial_shares = {
        "late_demand_detection": 35.0,
        "stale_allocation_censored_loop": 40.0,
        "single_source_pulp_rationing": 25.0,
    }
    assert sum(initial_shares.values()) == 100.0

    # Change late demand to 40.0% (max)
    new_shares, is_valid, msg = redistribute_root_causes("late_demand_detection", 40.0, initial_shares)
    assert is_valid is True
    assert round(sum(new_shares.values()), 1) == 100.0
    assert new_shares["late_demand_detection"] == 40.0
    assert 35.0 <= new_shares["stale_allocation_censored_loop"] <= 45.0
    assert 20.0 <= new_shares["single_source_pulp_rationing"] <= 30.0

    # Test exposures calculation
    exposures = calculate_root_cause_exposures(new_shares)
    assert exposures["shares_sum_pct"] == 100.0
    assert exposures["total_stockout_lost_revenue_inr_cr"] == 46.08
    assert "disclaimer" in exposures
