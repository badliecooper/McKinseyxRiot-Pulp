"""Tests for Scenario Replay, co-packer constraints, and deterministic passionfruit pulp rationing."""

import pytest
from services.scenario_service import ScenarioService
from config.business_rules import COPACKER_COST_PREMIUM_PCT


def test_copacker_feasibility_rules():
    """Verify that:
    1. Co-packer is rejected if raw pulp is unavailable (co-packer cannot solve pulp scarcity).
    2. Co-packer is rejected if notice < 14 days.
    3. Production premium is +25%.
    """
    svc = ScenarioService()

    # Case 1: Pulp unavailable -> Must reject
    res_no_pulp = svc.evaluate_copacker_feasibility(
        requested_additional_bottles=500000,
        notice_days_available=20,
        pulp_availability_flag=False,
    )
    assert res_no_pulp["is_feasible"] is False
    assert "INSUFFICIENT_RAW_PULP" in res_no_pulp["rejection_reason"]

    # Case 2: Notice < 14 days -> Must reject
    res_late = svc.evaluate_copacker_feasibility(
        requested_additional_bottles=500000,
        notice_days_available=10,
        pulp_availability_flag=True,
    )
    assert res_late["is_feasible"] is False
    assert "INSUFFICIENT_NOTICE" in res_late["rejection_reason"]

    # Case 3: Notice >= 14d and pulp available -> Feasible with +25% premium
    res_ok = svc.evaluate_copacker_feasibility(
        requested_additional_bottles=500000,
        notice_days_available=14,
        pulp_availability_flag=True,
    )
    assert res_ok["is_feasible"] is True
    assert res_ok["production_premium_pct"] == COPACKER_COST_PREMIUM_PCT


def test_passionfruit_pulp_contribution_efficiency():
    """Verify that PR-DP yields 2.0x higher contribution per kg of pulp than PR-PP."""
    svc = ScenarioService()
    sim = svc.simulate_passionfruit_disruption(
        closure_weeks=3,
        starting_cover_days=14,
        rationing_strategy="CONTRIBUTION_OPTIMIZED",
    )

    # PR-DP contribution per kg pulp = ₹548.57
    # PR-PP contribution per kg pulp = ₹274.29
    assert sim["pr_dp_contribution_per_kg_pulp_inr"] == 548.57
    assert sim["pr_pp_contribution_per_kg_pulp_inr"] == 274.29
    assert sim["contribution_ratio_dp_vs_pp"] == 2.0
