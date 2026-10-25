"""Alarms & Recommendations API endpoints for RIOT RADAR."""

import datetime
from typing import Dict, List, Optional, Any
from fastapi import APIRouter, HTTPException, Query
import pandas as pd

import tools
import approval
from services.csv_store import load_csv
from api.schemas import (
    AlarmItem,
    AlarmActionRequest,
    ApprovalDecisionRequest,
)

router = APIRouter(prefix="", tags=["Alarms & Recommendations"])


# ==============================================================================
# ALARMS
# ==============================================================================
@router.get("/alarms")
def get_alarms(
    severity: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    depot_id: Optional[str] = Query(None),
):
    """Retrieve list of rule-driven exception alarms with unread badge count."""
    df = load_csv("alarms")
    if df.empty:
        return {"alarms": [], "total": 0, "unread_count": 0}

    # Calculate unread count across active alarms
    unread_count = 0
    if "is_read" in df.columns:
        unread_count = int((df["is_read"].isin([False, "False", "0", 0]) & (df["status"] != "RESOLVED")).sum())
    else:
        unread_count = int((df["status"] == "NEW").sum())

    if severity:
        df = df[df["severity"] == severity]
    if status:
        df = df[df["status"] == status]
    if depot_id:
        df = df[df["depot_id"] == depot_id]

    records = df.replace({pd.NA: None, float("nan"): None}).to_dict(orient="records")
    return {"alarms": records, "total": len(records), "unread_count": unread_count}


@router.get("/alarms/{alarm_id}")
def get_single_alarm(alarm_id: str):
    """Retrieve a single alarm by ID."""
    df = load_csv("alarms")
    match = df[df["alarm_id"] == alarm_id]
    if match.empty:
        raise HTTPException(status_code=404, detail=f"Alarm {alarm_id} not found.")
    return match.iloc[0].to_dict()


@router.post("/alarms/{alarm_id}/mark-read")
def post_mark_alarm_read(alarm_id: str):
    """Mark a specific alarm as read to clear unread badge."""
    success = tools._risk_svc.mark_alarm_read(alarm_id=alarm_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Alarm {alarm_id} not found.")
    return {"status": "SUCCESS", "alarm_id": alarm_id, "is_read": True}


@router.post("/alarms/mark-all-read")
def post_mark_all_alarms_read():
    """Mark all active alarms as read."""
    tools._risk_svc.mark_all_alarms_read()
    return {"status": "SUCCESS", "message": "All alarms marked as read."}


@router.post("/alarms/{alarm_id}/acknowledge")
def post_acknowledge_alarm(alarm_id: str, req: AlarmActionRequest):
    """Acknowledge an alarm (NEW -> ACKNOWLEDGED). Does NOT approve any operational action."""
    success = tools._risk_svc.acknowledge_alarm(alarm_id=alarm_id, actor_id=req.actor_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Alarm {alarm_id} not found or failed to update.")
    return {"status": "SUCCESS", "alarm_id": alarm_id, "new_state": "ACKNOWLEDGED"}


@router.post("/alarms/{alarm_id}/resolve")
def post_resolve_alarm(alarm_id: str, req: AlarmActionRequest):
    """Mark an alarm as RESOLVED."""
    success = tools._risk_svc.resolve_alarm(alarm_id=alarm_id, notes=req.notes or "Resolved via API.")
    if not success:
        raise HTTPException(status_code=404, detail=f"Alarm {alarm_id} not found or failed to update.")
    return {"status": "SUCCESS", "alarm_id": alarm_id, "new_state": "RESOLVED"}


# ==============================================================================
# RECOMMENDATIONS & LANGGRAPH WORKFLOWS
# ==============================================================================
@router.post("/agent/detect")
def trigger_detection_pipeline(
    sku_id: Optional[str] = Query(None),
    depot_id: Optional[str] = Query(None),
):
    """Execute the 6-node LangGraph anomaly detection and recommendation pipeline."""
    res = tools.run_pipeline(sku_id=sku_id, depot_id=depot_id)
    return {
        "status": res.get("status", "COMPLETED"),
        "run_id": res.get("run_id"),
        "anomalies_detected": res.get("anomalies_detected", []),
        "recommendations_generated": res.get("recommendations_generated", []),
    }


@router.get("/recommendations")
def get_recommendations(status: Optional[str] = Query(None)):
    """Retrieve recommendations from recommendations.csv with optional status filter."""
    df = load_csv("recommendations")
    if df.empty:
        return {"recommendations": [], "total": 0}

    if status:
        df = df[df["status"] == status.upper()]

    # Sort PENDING first
    df = df.sort_values("created_at", ascending=False)
    records = df.replace({pd.NA: None, float("nan"): None}).to_dict(orient="records")
    return {"recommendations": records, "total": len(records)}


@router.get("/recommendations/{recommendation_id}")
def get_single_recommendation(recommendation_id: str):
    """Retrieve a single recommendation ticket by ID."""
    df = load_csv("recommendations")
    match = df[df["recommendation_id"] == recommendation_id]
    if match.empty:
        raise HTTPException(status_code=404, detail=f"Recommendation {recommendation_id} not found.")
    return match.iloc[0].to_dict()


@router.post("/recommendations/{recommendation_id}/decision")
def post_approval_decision(recommendation_id: str, req: ApprovalDecisionRequest):
    """Submit human approval decision (APPROVE, MODIFY, REJECT) to 3-node LangGraph approval pipeline."""
    res = approval.decide(
        recommendation_id=recommendation_id,
        decision=req.decision,
        approver_id=req.approver_id,
        approver_role=req.approver_role,
        modified_quantity_bottles=req.modified_quantity_bottles,
        notes=req.notes,
    )
    if not res.get("is_valid_decision"):
        raise HTTPException(status_code=400, detail=res.get("error_message", "Invalid approval decision."))

    res["success"] = True
    res["decision_status"] = res.get("persisted_status", req.decision)
    return res
