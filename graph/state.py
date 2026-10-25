"""Typed state schemas for LangGraph StateGraph in RIOT RADAR."""

from typing import Dict, List, Optional, Any
from typing_extensions import TypedDict


class DetectionState(TypedDict, total=False):
    """State for the 6-node autonomous anomaly detection and recommendation pipeline."""
    run_id: str
    timestamp: str
    target_sku_id: Optional[str]
    target_depot_id: Optional[str]
    signals_ingested_count: int
    anomalies_detected: List[Dict[str, Any]]
    risks_diagnosed: List[Dict[str, Any]]
    forecasts_adjusted: List[Dict[str, Any]]
    allocation_evaluations: List[Dict[str, Any]]
    recommendations_generated: List[Dict[str, Any]]
    status: str
    error_message: Optional[str]


class ApprovalState(TypedDict, total=False):
    """State for the 3-node human-in-the-loop approval decision pipeline."""
    approval_id: str
    recommendation_id: str
    decision: str  # "APPROVE", "MODIFY", "REJECT"
    approver_id: str
    approver_role: str
    modified_quantity_bottles: Optional[int]
    notes: Optional[str]
    decided_at: str
    is_valid_decision: bool
    persisted_status: str
    audit_event_id: str
    summary_message: str
    error_message: Optional[str]
