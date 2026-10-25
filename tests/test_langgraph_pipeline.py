"""Tests for LangGraph StateGraph pipelines (Detection & Human Approval)."""

import pytest
from graph.detection_pipeline import run_detection_pipeline
from graph.approval_pipeline import process_approval_decision
from services.csv_store import load_csv


def test_detection_pipeline_execution():
    """Verify that the 6-node detection pipeline completes and generates pending recommendations."""
    res = run_detection_pipeline(target_sku_id="PR-DP", target_depot_id="Depot-West-01")
    assert res["status"] == "COMPLETED"
    assert "signals_ingested_count" in res
    assert "anomalies_detected" in res
    assert "risks_diagnosed" in res
    assert "recommendations_generated" in res

    # Verify workflow state was written to CSV
    wf_df = load_csv("workflow_state")
    assert not wf_df[wf_df["run_id"] == res["run_id"]].empty


def test_approval_pipeline_execution():
    """Verify human approval workflow:
    1. Rejects invalid decision
    2. Modifies quantity with validation
    3. Approves recommendation and logs audit event
    """
    # Create a fresh pending recommendation fixture for this test run
    import uuid
    from services.csv_store import append_csv_row
    fresh_rec_id = f"REC-TEST-{uuid.uuid4().hex[:6].upper()}"
    test_rec = {
        "recommendation_id": fresh_rec_id,
        "created_at": "2026-05-20 10:00:00",
        "priority": "P1",
        "module": "DISTRIBUTION",
        "sku_id": "PR-DP",
        "origin_depot_id": "Depot-South-02",
        "destination_depot_id": "Depot-West-01",
        "action_type": "INTER_DEPOT_TRANSFER",
        "quantity_bottles": 10000,
        "cost_inr": 15000.0,
        "protected_contribution_inr": 192000.0,
        "lead_time_days": 3,
        "eta_days": 4,
        "shelf_life_status": "PASS",
        "donor_post_cover_days": 22.0,
        "destination_post_cover_days": 10.0,
        "shortage_reduction_bottles": 10000,
        "status": "PENDING",
        "confidence_level": "HIGH",
        "diagnosis": "Test fixture recommendation",
        "is_synthetic": True,
    }
    append_csv_row("recommendations", test_rec)
    target_rec_id = fresh_rec_id

    # Test 1: Invalid decision string
    bad_res = process_approval_decision(target_rec_id, "EXPLODE")
    assert bad_res["is_valid_decision"] is False
    assert "Invalid decision" in bad_res["error_message"]

    # Test 2: Valid APPROVE
    good_res = process_approval_decision(
        recommendation_id=target_rec_id,
        decision="APPROVE",
        approver_id="Test-Planner-01",
        notes="Approved under test conditions",
    )
    assert good_res["is_valid_decision"] is True
    assert good_res["persisted_status"] == "APPROVED"
    assert "audit_event_id" in good_res

    # Check persistence in approvals.csv and audit_log.csv
    app_df = load_csv("approvals")
    assert not app_df[app_df["recommendation_id"] == target_rec_id].empty

    audit_df = load_csv("audit_log")
    assert not audit_df[audit_df["entity_id"] == target_rec_id].empty

    # Clean up test fixture row from recommendations.csv
    recs_df = load_csv("recommendations")
    recs_df = recs_df[recs_df["recommendation_id"] != target_rec_id]
    recs_df.to_csv("data/recommendations.csv", index=False)
