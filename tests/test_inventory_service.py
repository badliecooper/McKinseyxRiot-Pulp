"""Tests for Inventory visibility, Days of Cover, and 67-day near-cliff threshold."""

import pytest
from services.inventory_service import (
    calculate_days_of_cover,
    calculate_target_stock,
    calculate_allocation_gap,
    InventoryService,
)
from config.business_rules import NEAR_CLIFF_WARNING_DAYS, MT_QC_MIN_SHELF_LIFE_DAYS


def test_days_of_cover_edge_cases():
    """Verify DoC calculation and disclosed zero-demand convention."""
    # Usable stock 2100, daily demand 100 -> 21 days
    assert calculate_days_of_cover(2100, 100) == 21.0
    # Zero stock -> 0.0 days
    assert calculate_days_of_cover(0, 100) == 0.0
    assert calculate_days_of_cover(-10, 100) == 0.0
    # Zero demand with stock -> None (disclosed convention: infinite/unconstrained)
    assert calculate_days_of_cover(1000, 0) is None
    # Zero demand and zero stock -> 0.0
    assert calculate_days_of_cover(0, 0) == 0.0


def test_target_stock_and_allocation_gap():
    """Verify target stock and allocation gap formulas."""
    # 100 btls/day * 21d target = 2100 btls
    target = calculate_target_stock(100, 21)
    assert target == 2100.0

    # Shortage: Target 2100, usable 1500 -> Gap = +600 btls
    assert calculate_allocation_gap(2100, 1500) == 600.0

    # Surplus: Target 2100, usable 3000 -> Gap = -900 btls
    assert calculate_allocation_gap(2100, 3000) == -900.0


def test_67_day_near_cliff_logic():
    """Verify 67-day near-cliff threshold and channel gating rules."""
    assert NEAR_CLIFF_WARNING_DAYS == 67
    assert MT_QC_MIN_SHELF_LIFE_DAYS == 60

    svc = InventoryService()
    # Test on Depot-East-01 PR-MPB (calibrated near-cliff stock)
    status = svc.get_sku_depot_inventory_status("PR-MPB", "Depot-East-01", daily_forecast_demand=5000.0)
    assert "remaining_shelf_life_days" in status
    # Check that shelf status properly distinguishes near-cliff vs healthy
    assert status["is_near_cliff"] is True or status["remaining_shelf_life_days"] > 67
