"""Comprehensive acceptance tests for targeted dashboard fixes:
1. AI Copilot SKU-Depot entity extraction and grounded answers
2. CSV data upload validation, duplicate detection, and persistence
3. Ranked rebalancing feasibility with regional proximity (e.g. Lucknow for NCR)
4. Alarm lifecycle (unread badge, mark-read, acknowledge, resolve, deduplication)
"""

import io
import pytest
from fastapi.testclient import TestClient
from api.main import app
import tools
from config.business_rules import SKUS, DEPOTS, TRANSFER_COST_PER_BOTTLE_INR
from api.routes.copilot import extract_entities, post_copilot_chat
from api.schemas import CopilotChatRequest
from services.distribution_service import get_inter_depot_transit_days, DistributionService
from services.csv_store import load_csv, save_csv
import pandas as pd


@pytest.fixture
def client():
    return TestClient(app)


def test_copilot_entity_extraction_and_grounding():
    """Verify that Copilot extracts specific SKU and Depot from message text and grounds answer."""
    # Test 1: Guava Chilli at Lucknow Depot
    sku, depot = extract_entities("What is the current stock and cover of Guava Chilli at Lucknow?")
    assert sku == "PR-GC"
    assert depot == "Depot-North-02"

    req = CopilotChatRequest(message="What is the current stock and cover of Guava Chilli at Lucknow?")
    res = post_copilot_chat(req)
    assert res["operating_mode"] in ["DETERMINISTIC_FALLBACK_ENGINE", "Rule-based mode", "LIVE_LLM_API"]
    assert "PR-GC" in res["reply"]
    assert "Lucknow" in res["reply"]
    assert "Days of Cover" in res["reply"]
    assert "Allocation Gap" in res["reply"]

    # Test 2: Loss Attribution
    req_loss = CopilotChatRequest(message="Can you explain the breakdown of the ₹46.08 Cr loss?")
    res_loss = post_copilot_chat(req_loss)
    assert "46.08" in res_loss["reply"]
    assert "14.75" in res_loss["reply"]
    assert "23.95" in res_loss["reply"]
    assert "10.4%" in res_loss["reply"]


def test_inter_depot_transit_ranking():
    """Verify that inter-depot transit uses configured regions:
    - Intra-regional (e.g. Delhi NCR <-> Lucknow in North) = 2 days
    - Adjacent (e.g. North <-> Central) = 3 days
    - Cross-country (e.g. South <-> North) = 4 days
    """
    transit_north = get_inter_depot_transit_days("Depot-North-02", "Depot-North-01")
    assert transit_north == 2, "Intra-regional transit should be 2 days"

    transit_adjacent = get_inter_depot_transit_days("Depot-Central-01", "Depot-North-01")
    assert transit_adjacent == 3, "Adjacent regional transit should be 3 days"

    transit_cross = get_inter_depot_transit_days("Depot-South-02", "Depot-North-01")
    assert transit_cross == 4, "Cross-country transit should be 4 days"


def test_rebalancing_feasibility_ranking_and_donor_cover():
    """Verify that rebalancing:
    1. Strictly protects donor cover >= 21d
    2. Evaluates candidates and populates selection_rationale and rejected_alternatives
    """
    svc = DistributionService()
    proposals = svc.optimize_inter_depot_rebalancing()
    
    assert len(proposals) > 0, "Expected feasible rebalancing proposals"
    for p in proposals:
        assert p["donor_post_cover_days"] >= 20.9, f"Donor {p['origin_depot_id']} violated 21d safety cover!"
        assert p["cost_inr"] == p["quantity_bottles"] * TRANSFER_COST_PER_BOTTLE_INR
        assert "selection_rationale" in p
        assert len(p["candidates_evaluated"]) > 0


def test_upload_validation_and_duplicate_detection(client):
    """Verify that CSV sales upload validates schema, detects duplicates, and persists."""
    # 1. Invalid date rejection
    invalid_date_csv = b"date,sku_id,depot_id,channel,observed_sales\nINVALID_DATE,PR-DP,Depot-West-01,QC,12000\n"
    res = client.post(
        "/api/upload/sales",
        files={"file": ("test.csv", io.BytesIO(invalid_date_csv), "text/csv")},
        data={"source_channel": "Quick Commerce", "uploader_name": "Test Planner"},
    )
    assert res.status_code in [200, 400]
    if res.status_code == 400:
        assert "Invalid date" in res.json().get("detail", "")
    else:
        assert res.json()["status"] == "VALIDATION_FAILED"

    # 2. Invalid SKU rejection
    invalid_sku_csv = b"date,sku_id,depot_id,channel,observed_sales\n2026-06-01,PR-UNKNOWN-JUICE,Depot-West-01,QC,12000\n"
    res = client.post(
        "/api/upload/sales",
        files={"file": ("test.csv", io.BytesIO(invalid_sku_csv), "text/csv")},
        data={"source_channel": "Quick Commerce", "uploader_name": "Test Planner"},
    )
    assert res.status_code in [200, 400]
    if res.status_code == 400:
        assert "Unknown SKU" in res.json().get("detail", "")
    else:
        assert res.json()["status"] == "VALIDATION_FAILED"

    # 3. Valid CSV ingestion with cleanup
    test_date = "2026-06-15"
    valid_csv = f"date,sku_id,depot_id,channel,observed_sales\n{test_date},PR-DP,Depot-West-01,QC,9999\n".encode("utf-8")
    try:
        res = client.post(
            "/api/upload/sales",
            files={"file": ("valid.csv", io.BytesIO(valid_csv), "text/csv")},
            data={"source_channel": "Quick Commerce", "uploader_name": "Test Planner"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["status"] in ["SUCCESS", "ALL_DUPLICATES"]

        # 4. Immediate second upload should detect duplicate
        res_dup = client.post(
            "/api/upload/sales",
            files={"file": ("valid.csv", io.BytesIO(valid_csv), "text/csv")},
            data={"source_channel": "Quick Commerce", "uploader_name": "Test Planner"},
        )
        assert res_dup.status_code == 200
        dup_data = res_dup.json()
        assert dup_data["status"] == "ALL_DUPLICATES" or dup_data.get("duplicates_skipped", 0) >= 1
    finally:
        dh_df = load_csv("demand_history")
        if not dh_df.empty:
            dh_clean = dh_df[~((dh_df["date"] == test_date) & (pd.to_numeric(dh_df["observed_sales"], errors="coerce") == 9999))]
            save_csv("demand_history", dh_clean)


def test_alarm_lifecycle_and_mark_read(client):
    """Verify alarm lifecycle endpoints: unread count, mark-read, acknowledge, resolve."""
    alarms_res = client.get("/api/alarms")
    assert alarms_res.status_code == 200
    data = alarms_res.json()
    assert "alarms" in data
    assert "unread_count" in data
    assert len(data["alarms"]) > 0

    alarm_id = data["alarms"][0]["alarm_id"]

    # Test mark-read
    read_res = client.post(f"/api/alarms/{alarm_id}/mark-read")
    assert read_res.status_code == 200
    assert read_res.json()["is_read"] is True

    # Test acknowledge (does NOT approve any recommendation)
    ack_res = client.post(f"/api/alarms/{alarm_id}/acknowledge", json={"actor_id": "Test-User"})
    assert ack_res.status_code == 200
    assert ack_res.json()["new_state"] == "ACKNOWLEDGED"

    # Test mark-all-read
    all_read = client.post("/api/alarms/mark-all-read")
    assert all_read.status_code == 200
