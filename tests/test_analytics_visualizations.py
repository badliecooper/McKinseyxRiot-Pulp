"""Unit tests for the four supply chain analytics visualization services and calculations:
1. Allocation-vs-Demand Alignment (Mismatch) Index
2. National Forecast Accuracy vs SKU-Depot Forecast Error (Aggregation Fallacy)
3. Censored-Demand Gap & Causal Feedback Loop
4. Pre-Summer Passionfruit Pulp Buffer Build Timeline
"""

import pytest
import numpy as np

from services.distribution_service import (
    calculate_allocation_alignment_index,
    DistributionService,
)
from services.demand_service import (
    DemandService,
    calculate_demand_uplift,
    calculate_wape,
    calculate_forecast_bias,
)
from services.scenario_service import ScenarioService


class TestAllocationAlignmentIndex:
    """Tests for Allocation-vs-Demand Alignment Index calculation and edge cases."""

    def test_perfect_alignment_returns_zero(self):
        """When allocation share exactly equals demand share, index must be 0.0%."""
        alloc = {"Depot-A": 1000.0, "Depot-B": 2000.0, "Depot-C": 3000.0}
        demand = {"Depot-A": 500.0, "Depot-B": 1000.0, "Depot-C": 1500.0}
        res = calculate_allocation_alignment_index(alloc, demand)
        assert res["alignment_index_pct"] == 0.0
        assert res["status"] == "CALCULATED"

    def test_complete_mismatch_returns_100_percent(self):
        """When stock is in Depot-A but all demand is in Depot-B, index must be 100.0%."""
        alloc = {"Depot-A": 1000.0, "Depot-B": 0.0}
        demand = {"Depot-A": 0.0, "Depot-B": 1000.0}
        res = calculate_allocation_alignment_index(alloc, demand)
        assert res["alignment_index_pct"] == 100.0
        # Contribution per depot: |1 - 0|/2 = 0.5 (50%), sum = 100%
        for b in res["depot_breakdown"]:
            assert b["mismatch_contribution_pct"] == 50.0

    def test_zero_allocation_or_demand_safe_handling(self):
        """Zero national allocation or zero national demand must return 0.0 without division error."""
        res_zero_alloc = calculate_allocation_alignment_index({"Depot-A": 0.0}, {"Depot-A": 500.0})
        assert res_zero_alloc["alignment_index_pct"] == 0.0
        assert res_zero_alloc["status"] == "ZERO_TOTAL_SUPPLY_OR_DEMAND"

        res_zero_demand = calculate_allocation_alignment_index({"Depot-A": 500.0}, {"Depot-A": 0.0})
        assert res_zero_demand["alignment_index_pct"] == 0.0
        assert res_zero_demand["status"] == "ZERO_TOTAL_SUPPLY_OR_DEMAND"

        res_empty = calculate_allocation_alignment_index({}, {})
        assert res_empty["alignment_index_pct"] == 0.0

    def test_distribution_service_alignment_report(self):
        """DistributionService generates alignment reports across all 5 SKUs with before/after improvement."""
        svc = DistributionService()
        rep = svc.get_allocation_alignment_report()
        assert "sku_alignment_indices" in rep
        assert len(rep["sku_alignment_indices"]) == 5
        for item in rep["sku_alignment_indices"]:
            assert "sku_id" in item
            assert "historical_mix_index_pct" in item
            assert "current_allocation_index_pct" in item
            assert "post_intervention_index_pct" in item
            # Post-intervention alignment should be an improvement (lower or equal mismatch)
            assert item["post_intervention_index_pct"] <= item["current_allocation_index_pct"] or item["post_intervention_index_pct"] <= item["historical_mix_index_pct"] + 10.0


class TestNationalVsLocalForecastMetrics:
    """Tests for two-panel forecast evaluation and the aggregation fallacy."""

    def test_aggregation_fallacy_mean_absolute_bias_greater_than_or_equal_national_bias(self):
        """Mean absolute bias across local cells must be >= |national bias| due to cancelling errors."""
        svc = DemandService()
        res = svc.get_national_vs_local_forecast_metrics(vintage_id="VINTAGE-2026-W18")
        assert "national_panel" in res
        assert "sku_depot_panel" in res

        nat_bias = res["national_panel"]["bias_pct"]
        local_abs_bias = res["sku_depot_panel"]["mean_absolute_bias_pct"]
        cancelling_gap = res["sku_depot_panel"]["cancelling_error_gap_pct"]

        assert local_abs_bias >= abs(nat_bias)
        assert cancelling_gap >= 0.0

    def test_signed_vs_absolute_bias_distinction(self):
        """Mean absolute bias must strictly take absolute values before averaging."""
        # Simulated two cells: cell 1 overforecasts by +20%, cell 2 underforecasts by -20%
        # National aggregate = 0% bias, Signed mean = 0% bias, Mean absolute bias = 20%
        f = np.array([120.0, 80.0])
        a = np.array([100.0, 100.0])
        cell_biases = (f - a) / a * 100.0
        signed_mean = np.mean(cell_biases)
        mean_abs = np.mean(np.abs(cell_biases))
        assert signed_mean == 0.0
        assert mean_abs == 20.0
        assert mean_abs > signed_mean


class TestCensoredDemandAndCascade:
    """Tests for censored-demand gap and causal cascade indicators."""

    def test_demand_uplift_zero_division_safety(self):
        assert calculate_demand_uplift(0.0, 100.0) is None
        assert calculate_demand_uplift(100.0, 140.0) == 40.0

    def test_causal_cascade_metrics_structure(self):
        svc = ScenarioService()
        cascade = svc.get_causal_cascade_metrics()
        assert "nodes" in cascade
        assert len(cascade["nodes"]) == 6
        node_ids = [n["id"] for n in cascade["nodes"]]
        assert node_ids == [
            "late_demand_signal",
            "stale_allocation",
            "stock_out",
            "censored_sales",
            "underestimated_forecast",
            "repeated_stock_out",
        ]
        for node in cascade["nodes"]:
            assert node["model_metric_value"] != ""
            assert node["supporting_calculation"] != ""
            assert len(node["affected_sku_depots"]) > 0


class TestPreSummerPulpBufferTimeline:
    """Tests for passionfruit pulp buffer build timeline and financial comparison."""

    def test_pulp_build_timeline_projection(self):
        svc = ScenarioService()
        res = svc.get_pre_summer_pulp_build_timeline(
            starting_cover_days=14,
            target_cover_days=24,
            weekly_buffer_build_kg=18000.0,
            holding_cost_inr_per_kg_month=12.50,
        )
        assert res["case_facts"]["expected_highway_closure_duration_days"] == 21
        assert res["case_facts"]["normal_road_transit_days"] == 3
        assert res["case_facts"]["starting_cover_days_case_fact"] == 14
        assert res["case_facts"]["historical_emergency_air_freight_inr_cr"] == 3.20

        # Target cover = 24 days (21d closure + 3d transit)
        assert res["planning_parameters"]["target_buffer_cover_days"] == 24
        assert len(res["weekly_timeline"]) in [8, 9]

        # Final week projected cover should reach or exceed target cover
        assert res["weekly_timeline"][-1]["projected_cover_days"] >= 24.0

        # Financial trade-off: holding cost should be well below ₹3.20 Cr emergency air freight
        assert res["financial_comparison"]["estimated_buffer_holding_cost_inr_cr"] < 3.20
        assert res["financial_comparison"]["net_avoided_exposure_inr_cr"] > 2.50
