"""Human-in-the-loop approval module for RIOT RADAR.

Enforces institutional governance:
1. Every operational recommendation requires explicit human approval.
2. The agent only proposes; only human decision controls can commit.
3. Records all approvals, modifications, and rejections into approvals.csv and audit_log.csv.
"""

from typing import Dict, List, Optional, Any
import pandas as pd

from services.csv_store import load_csv
from graph.approval_pipeline import process_approval_decision


def decide(
    recommendation_id: str,
    decision: str,
    approver_id: str = "Central-Planner-01",
    approver_role: str = "Lead Supply Chain Planner",
    modified_quantity_bottles: Optional[int] = None,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute human approval decision on a recommendation ticket.
    
    Allowed decisions: "APPROVE", "MODIFY", "REJECT".
    """
    return process_approval_decision(
        recommendation_id=recommendation_id,
        decision=decision,
        approver_id=approver_id,
        approver_role=approver_role,
        modified_quantity_bottles=modified_quantity_bottles,
        notes=notes,
    )


def get_pending_recommendations() -> pd.DataFrame:
    """Retrieve all recommendations currently awaiting human approval."""
    df = load_csv("recommendations")
    if df.empty:
        return df
    return df[df["status"] == "PENDING"].sort_values("created_at", ascending=False)


def get_approval_history() -> pd.DataFrame:
    """Retrieve complete audit history of all recorded human decisions."""
    return load_csv("approvals")
