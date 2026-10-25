"""Automated tests for inventory reconciliation, stock-out date calculations,
receipt-driven cover increases, and scenario date consistency.

Audits:
1. Mathematical identity: Closing = Opening + Inbounds + Transfers - Fulfilled.
2. Demand fulfillment constraint: Fulfilled <= Available Usable Stock; Excess = Unmet Demand.
3. Deterministic stock-out date definition: First date where Closing == 0 and Unmet > 0.
4. Positive cover jump audit: Every cover increase MUST be backed by an annotated receipt/transfer.
5. Scenario parity: Identical opening balances (83,150 btls), demand series, and evaluation horizons.
6. Calibrated event dates: 17-day detection advantage (2026-05-20 vs 2026-06-06).
"""

import pytest
import datetime
import pandas as pd

from services.csv_store import load_csv
from services.scenario_service import ScenarioService
from services.inventory_service import InventoryService


@pytest.fixture
def scenario_svc():
    return ScenarioService()


@pytest.fixture
def inventory_svc():
    return InventoryService()


def test_inventory_opening_snapshot_validity():
    """Verify that inventory.csv provides a valid opening snapshot dated 2026-05-20."""
    inv_df = load_csv("inventory")
    assert not inv_df.empty, "inventory.csv must not be empty"

    # All snapshot audit dates must be 2026-05-20
    assert (inv_df["last_audit_date"] == "2026-05-20").all(), "All inventory snapshots must be dated 2026-05-20"

    # PR-DP @ Depot-West-01 opening stock
    match = inv_df[(inv_df["sku_id"] == "PR-DP") & (inv_df["depot_id"] == "Depot-West-01")]
    assert not match.empty
    opening_stock = float(match.iloc[0]["total_usable_stock"])
    assert opening_stock == 83150.0, "PR-DP @ Depot-West-01 opening stock must be exactly 83,150 btls"


def test_inventory_reconciliation_identity(scenario_svc):
    """Verify that for every day t in both Historical and RIOT RADAR ledgers:
    Closing_t == Opening_t + Inbounds_t + Transfers_t - Fulfilled_t
    and Opening_t == Closing_{t-1} for t > 1.
    """
    res = scenario_svc.generate_deterministic_scenario_ledger("PR_DP_VIRAL_SPIKE")
    assert "historical_ledger" in res
    assert "radar_ledger" in res

    for ledger_key in ["historical_ledger", "radar_ledger"]:
        ledger = res[ledger_key]
        assert len(ledger) == 21, "Evaluation horizon must be exactly 21 days"

        for i, row in enumerate(ledger):
            # Check continuity
            if i > 0:
                prev_closing = ledger[i - 1]["closing_stock"]
                assert row["opening_stock"] == prev_closing, (
                    f"{ledger_key} Day {row['day']}: Opening ({row['opening_stock']}) "
                    f"does not match previous Closing ({prev_closing})"
                )

            # Available stock identity
            expected_avail = row["opening_stock"] + row["inbound_receipt_qty"] + row["transfer_in_qty"]
            assert row["available_usable_stock"] == expected_avail, (
                f"{ledger_key} Day {row['day']}: Available stock identity violated"
            )

            # Closing stock identity
            expected_closing = expected_avail - row["fulfilled_demand"]
            assert row["closing_stock"] == expected_closing, (
                f"{ledger_key} Day {row['day']}: Closing stock identity violated: "
                f"Closing={row['closing_stock']} vs Expected={expected_closing}"
            )


def test_fulfilled_capped_at_available_and_unmet_demand(scenario_svc):
    """Verify that Fulfilled <= Available and Fulfilled + Unmet == Daily Demand."""
    res = scenario_svc.generate_deterministic_scenario_ledger("PR_DP_VIRAL_SPIKE")

    for ledger_key in ["historical_ledger", "radar_ledger"]:
        for row in res[ledger_key]:
            avail = row["available_usable_stock"]
            fulfilled = row["fulfilled_demand"]
            unmet = row["unmet_demand"]
            demand = row["daily_demand"]

            # Constraint 1: Fulfilled cannot exceed available usable stock
            assert fulfilled <= avail, (
                f"{ledger_key} Day {row['day']}: Fulfilled ({fulfilled}) exceeds available ({avail})"
            )

            # Constraint 2: Fulfilled + Unmet == Gross Demand
            assert fulfilled + unmet == demand, (
                f"{ledger_key} Day {row['day']}: Fulfilled + Unmet ({fulfilled + unmet}) != Demand ({demand})"
            )

            # Constraint 3: When available is 0, fulfilled must be 0 and unmet == demand
            if avail == 0:
                assert fulfilled == 0, f"{ledger_key} Day {row['day']}: Fulfilled should be 0 when available is 0"
                assert unmet == demand, f"{ledger_key} Day {row['day']}: Unmet should equal full demand when available is 0"


def test_projected_stockout_date_calculation(scenario_svc, inventory_svc):
    """Verify stock-out date calculation: first date where closing stock reaches 0 and unmet > 0."""
    res = scenario_svc.generate_deterministic_scenario_ledger("PR_DP_VIRAL_SPIKE")
    h_ledger = res["historical_ledger"]

    # In historical policy, stock runs out on Day 6 (2026-05-25)
    # Day 5 closing is 17,693; Day 6 demand is 18,819 -> unmet = 1,126 btls, closing = 0.
    day6 = h_ledger[5]
    assert day6["date"] == "2026-05-25"
    assert day6["is_stocked_out"] is True
    assert day6["unmet_demand"] > 0
    assert day6["closing_stock"] == 0

    assert res["summary"]["historical_projected_stockout_date"] == "2026-05-25"

    # Under RIOT RADAR proactive policy, early transfer REC-2026-0520-001 arrives on Day 5 (2026-05-24)
    # Day 6 stock is positive (16,874 btls) and stockout on May 25 is averted!
    radar_day6 = res["radar_ledger"][5]
    assert radar_day6["closing_stock"] > 0, "RIOT RADAR must keep Day 6 stock positive"
    assert radar_day6["is_stocked_out"] is False


def test_receipt_driven_cover_increases_annotated(scenario_svc):
    """Investigate every cover increase and require an annotated receipt or transfer."""
    res = scenario_svc.generate_deterministic_scenario_ledger("PR_DP_VIRAL_SPIKE")

    for ledger_key in ["historical_ledger", "radar_ledger"]:
        ledger = res[ledger_key]
        for i in range(1, len(ledger)):
            curr = ledger[i]
            prev = ledger[i - 1]

            # If cover increased
            if curr["days_of_cover"] > prev["days_of_cover"]:
                # Must be driven by non-zero inbound receipt or transfer
                total_inflow = curr["inbound_receipt_qty"] + curr["transfer_in_qty"]
                assert total_inflow > 0, (
                    f"{ledger_key} Day {curr['day']} has unexplained cover increase from "
                    f"{prev['days_of_cover']} to {curr['days_of_cover']} with 0 inflow!"
                )
                # Must be annotated with intervention note
                assert curr["intervention_note"] != "", (
                    f"{ledger_key} Day {curr['day']} has cover increase without an annotated note!"
                )


def test_identical_baseline_inputs(scenario_svc):
    """Verify that Historical Policy and RIOT RADAR share identical opening balance,
    demand assumptions, and scheduled inbounds.
    """
    res = scenario_svc.generate_deterministic_scenario_ledger("PR_DP_VIRAL_SPIKE")
    h_ledger = res["historical_ledger"]
    r_ledger = res["radar_ledger"]

    # 1. Identical opening balance
    assert h_ledger[0]["opening_stock"] == r_ledger[0]["opening_stock"] == 83150

    # 2. Identical daily demand series for all 21 days
    for d in range(21):
        assert h_ledger[d]["daily_demand"] == r_ledger[d]["daily_demand"]

    # 3. Identical scheduled inbound SHP-2026-0518-11 on Day 3 (2026-05-22)
    assert h_ledger[2]["inbound_receipt_qty"] == r_ledger[2]["inbound_receipt_qty"] == 32000

    # 4. Trajectory diverges on Day 5 (2026-05-24) due to RIOT RADAR transfer arrival
    assert h_ledger[4]["transfer_in_qty"] == 0
    assert r_ledger[4]["transfer_in_qty"] == 18000
    assert "REC-2026-0520-001" in r_ledger[4]["intervention_note"]


def test_scenario_date_consistency_and_detection_advantage(scenario_svc):
    """Verify that event dates maintain logical ordering and the 17-day detection advantage:
    First Signal (2026-05-18) <= Agent Flag (2026-05-20) <= Approval (2026-05-21)
    <= Transfer Arrival (2026-05-24) < Historical Planner Notice (2026-06-06).
    """
    events = scenario_svc.get_scenario_timeline_comparison("PR_DP_VIRAL_SPIKE")

    d_sig = datetime.date.fromisoformat(events["first_qc_signal_date"])
    d_flag = datetime.date.fromisoformat(events["agent_flag_date"])
    d_appr = datetime.date.fromisoformat(events["human_approval_date"])
    d_arr = datetime.date.fromisoformat(events["transfer_arrival_date"])
    d_notice = datetime.date.fromisoformat(events["historical_planner_notice_date"])

    assert d_sig <= d_flag, "First signal must be prior to or on agent flag date"
    assert d_flag < d_appr, "Human approval must reflect 24h governance latency"
    assert d_appr < d_arr, "Transfer arrival must reflect 3d transit lead time"
    assert d_arr < d_notice, "Mitigation must arrive well before historical planner notice"

    detection_lag_days = (d_notice - d_flag).days
    assert detection_lag_days == 17, f"Detection advantage must be exactly 17 days, got {detection_lag_days}"
    assert events["detection_advantage_days"] == 17
