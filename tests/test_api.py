"""FastAPI Endpoint Integration Tests for RIOT RADAR."""

import pytest
from starlette.testclient import TestClient
from api.main import app

client = TestClient(app)


def test_api_health():
    """Verify /api/health returns 200 with database and operating mode metadata."""
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "HEALTHY"
    assert data["database_mode"] == "CSV_ONLY_PERSISTENCE"
    assert "operating_mode" in data


def test_api_control_tower_kpis_and_ribbon():
    """Verify Control Tower ribbon and 6 national KPIs."""
    res_ribbon = client.get("/api/control-tower/health-ribbon")
    assert res_ribbon.status_code == 200
    ribbon = res_ribbon.json()
    assert "Demand" in ribbon
    assert "Supply" in ribbon
    assert "Inventory" in ribbon
    assert "Distribution" in ribbon
    assert "Transportation" in ribbon

    res_kpis = client.get("/api/control-tower/kpis")
    assert res_kpis.status_code == 200
    kpis = res_kpis.json()
    assert "depots_at_risk" in kpis
    assert "forecast_wape_pct" in kpis
    assert "projected_shortage_bottles" in kpis
    assert "transfer_opportunities_count" in kpis
    assert "detection_lead_time_days" in kpis
    assert "pending_decisions_count" in kpis


def test_api_45_sku_depot_grid():
    """Verify /api/sku-depot returns all 45 operational combinations."""
    res = client.get("/api/sku-depot")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 45
    assert len(data["data"]) == 45
    # Verify no NaN or raw float null issues
    first = data["data"][0]
    assert "sku_id" in first
    assert "depot_id" in first
    assert "days_of_cover" in first


def test_api_heatmap_and_risk_matrix():
    """Verify heatmap and risk matrix endpoints."""
    res_hm = client.get("/api/control-tower/heatmap?metric=allocation_gap")
    assert res_hm.status_code == 200
    hm = res_hm.json()
    assert len(hm["columns"]) == 5  # 5 SKUs
    assert len(hm["rows"]) == 9     # 9 Depots
    assert len(hm["matrix"]) == 9

    res_rm = client.get("/api/control-tower/risk-matrix")
    assert res_rm.status_code == 200
    rm = res_rm.json()
    assert len(rm["points"]) == 45
    assert "thresholds" in rm


def test_api_loss_attribution_and_redistribute():
    """Verify loss attribution non-overlapping categories and redistribution."""
    res = client.get("/api/control-tower/loss-attribution")
    assert res.status_code == 200
    loss = res.json()
    assert loss["stockout_lost_revenue_inr_cr"] == 46.08
    assert loss["foregone_contribution_inr_cr"] == 14.75
    assert loss["bottom_line_exposure_inr_cr"] == 23.95
    assert loss["year_1_system_budget_cap_inr_cr"] == 2.50
    assert loss["break_even_recovery_hurdle_pct"] == 10.4

    # Test redistribution request
    req_body = {
        "changed_cause_key": "late_demand_detection",
        "new_value_pct": 38.0,
        "current_shares": {
            "late_demand_detection": 35.0,
            "stale_allocation_censored_loop": 40.0,
            "single_source_pulp_rationing": 25.0,
        },
    }
    res_redist = client.post("/api/control-tower/loss-attribution/redistribute", json=req_body)
    assert res_redist.status_code == 200
    redist_data = res_redist.json()
    assert redist_data["shares_sum_pct"] == 100.0


def test_api_scenario_replay():
    """Verify /api/scenarios/replay returns deterministic waterfall and daily timeline."""
    req_body = {
        "scenario_id": "PR_DP_VIRAL_SPIKE",
    }
    res = client.post("/api/scenarios/replay", json=req_body)
    assert res.status_code == 200
    data = res.json()
    assert data["kpis"]["detection_advantage_days"] == 17
    assert "waterfall" in data
    assert len(data["daily_cover_comparison"]) == 21


def test_api_weekly_report_preview():
    """Verify /api/reports/weekly/preview returns structured briefing."""
    res = client.get("/api/reports/weekly/preview?week=2026-W18")
    assert res.status_code == 200
    data = res.json()
    assert data["report_week"] == "2026-W18"
    assert "key_metrics" in data
    assert "executive_summary" in data


def test_api_alarms_lifecycle():
    """Verify alarms listing, acknowledge, and resolve workflow."""
    res = client.get("/api/alarms")
    assert res.status_code == 200
    data = res.json()
    assert "alarms" in data
    alarms = data["alarms"]
    assert len(alarms) > 0
    alarm_id = alarms[0]["alarm_id"]

    # Acknowledge
    res_ack = client.post(f"/api/alarms/{alarm_id}/acknowledge", json={"actor_id": "COO"})
    assert res_ack.status_code == 200
    assert res_ack.json()["new_state"] == "ACKNOWLEDGED"

    # Resolving alarm does NOT approve any recommendation silently
    res_res = client.post(f"/api/alarms/{alarm_id}/resolve", json={"actor_id": "COO", "notes": "Verified mitigation"})
    assert res_res.status_code == 200
    assert res_res.json()["new_state"] == "RESOLVED"


def test_api_recommendation_decision_flow():
    """Verify recommendation decision workflow through process_approval_decision."""
    from services.csv_store import append_csv_row
    import uuid

    # Inject a unique test recommendation
    rec_id = f"REC-API-TEST-{uuid.uuid4().hex[:6]}"
    test_rec = {
        "recommendation_id": rec_id,
        "created_at": "2026-05-15T08:00:00",
        "priority": "P2",
        "module": "DISTRIBUTION",
        "sku_id": "PR-OR",
        "origin_depot_id": "Depot-South-01",
        "destination_depot_id": "Depot-East-01",
        "action_type": "INTER_DEPOT_TRANSFER",
        "quantity_bottles": 5000,
        "cost_inr": 7500.0,
        "protected_contribution_inr": 96000.0,
        "lead_time_days": 3,
        "eta_days": 4,
        "shelf_life_status": "PASS",
        "donor_post_cover_days": 24.5,
        "destination_post_cover_days": 18.2,
        "shortage_reduction_bottles": 5000,
        "status": "PENDING",
        "confidence_level": "HIGH",
        "diagnosis": "API test transfer",
        "is_synthetic": True,
    }
    append_csv_row("recommendations", test_rec)

    # Approve via API
    decision_payload = {
        "decision": "APPROVE",
        "approver_id": "COO-Lead",
        "approver_role": "COO",
        "modified_quantity_bottles": None,
        "notes": "Approved for transfer",
    }
    res = client.post(f"/api/recommendations/{rec_id}/decision", json=decision_payload)
    assert res.status_code == 200
    res_data = res.json()
    assert res_data["success"] is True
    assert res_data["decision_status"] == "APPROVED"

    # Duplicate decision must fail
    res_dup = client.post(f"/api/recommendations/{rec_id}/decision", json=decision_payload)
    assert res_dup.status_code == 400


def test_api_copilot_chat():
    """Verify copilot chat returns grounded responses without requiring LLM key."""
    chat_payload = {
        "message": "What is the status of PR-DP at Depot-West-01?",
    }
    res = client.post("/api/copilot/chat", json=chat_payload)
    assert res.status_code == 200
    data = res.json()
    assert "reply" in data
    assert data["operating_mode"] == "DETERMINISTIC_FALLBACK_ENGINE"
    assert len(data["grounded_evidence"]) > 0


def test_api_manual_stockout_report():
    """Verify manual stockout report submission."""
    report_payload = {
        "depot_id": "Depot-North-01",
        "sku_id": "PR-DP",
        "channel": "Quick Commerce",
        "estimated_unmet_bottles": 12000,
        "reported_by": "Regional Planner",
        "evidence_source": "Zepto dark store logs",
        "notes": "Zepto dark store surge reported",
    }
    res = client.post("/api/stockout-reports", json=report_payload)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "report_id" in data


def test_api_invalid_depot_rejected_safely():
    """Verify invalid depot or SKU IDs are rejected safely."""
    res = client.get("/api/sku-depot/detail?depot_id=INVALID_DEPOT&sku_id=PR-DP")
    assert res.status_code == 404

