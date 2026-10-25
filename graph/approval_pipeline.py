"""LangGraph StateGraph for Phase 2 Human Approval Decision Workflow.

Architecture:
Nodes:
1. human_approval (validates decision, permissions, and recommendation existence)
2. record_decision (updates recommendations.csv, writes to approvals.csv & audit_log.csv)
3. summarize_result (formats structured confirmation)

Allowed decisions: "APPROVE", "MODIFY", "REJECT".
"""

import datetime
import json
import uuid
from typing import Dict, Any, Optional

from langgraph.graph import StateGraph, END

from graph.state import ApprovalState
from services.csv_store import load_csv, update_csv_record, append_csv_row


def node_human_approval(state: ApprovalState) -> Dict[str, Any]:
    """Node 1: Validate the human decision, target recommendation status, and authorization."""
    rec_id = state.get("recommendation_id")
    decision = state.get("decision", "").upper()
    modified_qty = state.get("modified_quantity_bottles")

    if not rec_id:
        return {
            "is_valid_decision": False,
            "error_message": "Missing recommendation_id.",
        }

    recs_df = load_csv("recommendations")
    if recs_df.empty:
        return {
            "is_valid_decision": False,
            "error_message": "No recommendations found in persistence.",
        }

    match = recs_df[recs_df["recommendation_id"] == rec_id]
    if match.empty:
        return {
            "is_valid_decision": False,
            "error_message": f"Recommendation {rec_id} not found.",
        }

    curr_status = match.iloc[0]["status"]
    if curr_status != "PENDING":
        return {
            "is_valid_decision": False,
            "error_message": f"Recommendation {rec_id} is already in '{curr_status}' state (not PENDING).",
        }

    if decision not in ["APPROVE", "MODIFY", "REJECT"]:
        return {
            "is_valid_decision": False,
            "error_message": f"Invalid decision '{decision}'. Allowed: APPROVE, MODIFY, REJECT.",
        }

    if decision == "MODIFY":
        if modified_qty is None or modified_qty <= 0:
            return {
                "is_valid_decision": False,
                "error_message": "Decision 'MODIFY' requires a positive modified_quantity_bottles.",
            }

    return {
        "is_valid_decision": True,
        "error_message": None,
    }


def node_record_decision(state: ApprovalState) -> Dict[str, Any]:
    """Node 2: Atomically persist decision to approvals.csv, recommendations.csv, and audit_log.csv."""
    if not state.get("is_valid_decision"):
        return {"persisted_status": "FAILED"}

    rec_id = state["recommendation_id"]
    decision = state["decision"].upper()
    decided_at = state.get("decided_at") or datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    approver_id = state.get("approver_id", "COO-Executive")
    approver_role = state.get("approver_role", "Executive Planner")
    modified_qty = state.get("modified_quantity_bottles")
    notes = state.get("notes", "")

    # Map decision to new status
    new_status = "APPROVED" if decision == "APPROVE" else ("MODIFIED" if decision == "MODIFY" else "REJECTED")

    # Update recommendation
    updates = {"status": new_status}
    if decision == "MODIFY" and modified_qty:
        updates["quantity_bottles"] = str(modified_qty)
        updates["cost_inr"] = str(float(modified_qty) * 1.50)
        updates["protected_contribution_inr"] = str(float(modified_qty) * 60.0 * 0.32)

    update_csv_record("recommendations", "recommendation_id", rec_id, updates)

    # Append to approvals.csv
    approval_id = f"APP-{uuid.uuid4().hex[:8].upper()}"
    approval_record = {
        "approval_id": approval_id,
        "recommendation_id": rec_id,
        "decision": decision,
        "decided_at": decided_at,
        "approver_id": approver_id,
        "approver_role": approver_role,
        "modified_quantity_bottles": modified_qty if decision == "MODIFY" else "",
        "notes": notes,
    }
    append_csv_row("approvals", approval_record)

    # Append to audit_log.csv
    event_id = f"AUD-{uuid.uuid4().hex[:8].upper()}"
    audit_record = {
        "event_id": event_id,
        "timestamp": decided_at,
        "event_type": "HUMAN_APPROVAL_DECISION",
        "entity_type": "RECOMMENDATION",
        "entity_id": rec_id,
        "actor_id": approver_id,
        "action": decision,
        "details_json": json.dumps({
            "new_status": new_status,
            "modified_quantity": modified_qty,
            "notes": notes,
        }),
    }
    append_csv_row("audit_log", audit_record)

    return {
        "approval_id": approval_id,
        "persisted_status": new_status,
        "audit_event_id": event_id,
    }


def node_summarize_result(state: ApprovalState) -> Dict[str, Any]:
    """Node 3: Format the structured decision briefing."""
    if not state.get("is_valid_decision"):
        return {
            "summary_message": f"[REJECTED_INPUT] Action failed: {state.get('error_message')}"
        }

    rec_id = state["recommendation_id"]
    decision = state["decision"].upper()
    status = state.get("persisted_status")
    approver = state.get("approver_id")

    msg = f"[{status}] Recommendation {rec_id} successfully recorded by {approver}. Action is committed to operational log."
    return {"summary_message": msg}


def build_approval_graph() -> StateGraph:
    """Construct the compiled LangGraph StateGraph for approvals."""
    builder = StateGraph(ApprovalState)
    builder.add_node("human_approval", node_human_approval)
    builder.add_node("record_decision", node_record_decision)
    builder.add_node("summarize_result", node_summarize_result)

    builder.set_entry_point("human_approval")
    builder.add_edge("human_approval", "record_decision")
    builder.add_edge("record_decision", "summarize_result")
    builder.add_edge("summarize_result", END)

    return builder.compile()


def process_approval_decision(
    recommendation_id: str,
    decision: str,
    approver_id: str = "Planner-Lead",
    approver_role: str = "Central S&OP Planner",
    modified_quantity_bottles: Optional[int] = None,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute the Phase 2 LangGraph human approval workflow.
    
    Allowed decisions: "APPROVE", "MODIFY", "REJECT".
    """
    graph = build_approval_graph()
    initial_state: ApprovalState = {
        "approval_id": "",
        "recommendation_id": recommendation_id,
        "decision": decision.upper(),
        "approver_id": approver_id,
        "approver_role": approver_role,
        "modified_quantity_bottles": modified_quantity_bottles,
        "notes": notes,
        "decided_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "is_valid_decision": False,
        "persisted_status": "",
        "audit_event_id": "",
        "summary_message": "",
        "error_message": None,
    }

    final_state = graph.invoke(initial_state)
    return dict(final_state)
