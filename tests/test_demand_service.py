"""Tests for Demand Intelligence, censored-demand detection, uplift, and WAPE."""

import pytest
import numpy as np
from services.demand_service import (
    calculate_demand_uplift,
    calculate_service_level_fill_rate,
    calculate_wape,
    calculate_forecast_bias,
    DemandService,
)


def test_demand_uplift_zero_handling():
    """Verify safe handling of zero or negative observed demand (preventing division by zero)."""
    assert calculate_demand_uplift(0, 100) is None
    assert calculate_demand_uplift(-5, 100) is None
    assert calculate_demand_uplift(None, 100) is None
    # Normal case: observed 100, corrected 150 -> 50% uplift
    assert calculate_demand_uplift(100, 150) == 50.0
    # No uplift: observed 100, corrected 100 -> 0%
    assert calculate_demand_uplift(100, 100) == 0.0


def test_wape_and_bias_calculations():
    """Verify WAPE and Forecast Bias calculations and safe zero handling."""
    forecast = [120, 100, 80]
    actual = [100, 100, 100]
    # Total actual = 300. Abs error = |20| + |0| + |-20| = 40. WAPE = 40/300 = 13.33%
    wape = calculate_wape(forecast, actual)
    assert round(wape, 2) == 13.33

    # Diff = 20 + 0 - 20 = 0. Bias = 0.0%
    bias = calculate_forecast_bias(forecast, actual)
    assert bias == 0.0

    # Overforecasting bias:
    f_over = [150, 150]
    a_over = [100, 100]
    assert calculate_forecast_bias(f_over, a_over) == 50.0

    # Zero actual: returns None
    assert calculate_wape([10, 20], [0, 0]) is None
    assert calculate_forecast_bias([10, 20], [0, 0]) is None


def test_service_level_fill_rate():
    """Verify fill rate calculation and bounds."""
    assert calculate_service_level_fill_rate(90, 100) == 90.0
    assert calculate_service_level_fill_rate(120, 100) == 100.0  # Capped at 100%
    assert calculate_service_level_fill_rate(0, 100) == 0.0
    assert calculate_service_level_fill_rate(50, 0) is None  # Safe zero denominator


def test_detect_and_correct_censored_demand():
    """Verify that demand service correctly detects censored stockout periods."""
    svc = DemandService()
    # Test on PR-DP @ Depot-West-01 (Mumbai viral spike & stockout)
    res = svc.detect_and_correct_censored_demand("PR-DP", "Depot-West-01", lookback_days=14)
    assert res["sku_id"] == "PR-DP"
    assert res["depot_id"] == "Depot-West-01"
    assert res["is_censored"] is True
    assert res["corrected_demand_sum"] > res["observed_demand_sum"]
    assert res["demand_uplift_pct"] is not None and res["demand_uplift_pct"] > 0
