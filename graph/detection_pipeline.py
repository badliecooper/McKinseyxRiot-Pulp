"""LangGraph StateGraph for Phase 1 Anomaly Detection & Recommendation Pipeline.

Architecture:
Nodes:
1. ingest_signal
2. detect_anomaly
3. diagnose_risk
4. forecast_demand
5. evaluate_allocation
6. generate_recommendation

Persists generated recommendations with status="PENDING" in data/recommendations.csv
and execution trace in data/workflow_state.csv.
"""

import datetime
import json
import uuid
from typing import Dict, Any, List, Optional

from langgraph.graph import StateGraph, END

from graph.state import DetectionState
from services.csv_store import append_csv_row, load_csv
from services.demand_service import DemandService
from services.distribution_service import DistributionService
from services.inventory_service import InventoryService
from services.risk_service import RiskService


def node_ingest_signal(state: DetectionState) -> Dict[str, Any]:
    """Node 1: Ingest latest multi-channel demand signals and supplier disruption flags."""
    demand_service = DemandService()
    df = demand_service.get_demand_history(
        sku_id=state.get("target_sku_id"),
        depot_id=state.get("target_depot_id"),
        days=7,
    )
    return {
        "signals_ingested_count": len(df),
        "status": "SIGNALS_INGESTED",
    }


def node_detect_anomaly(state: DetectionState) -> Dict[str, Any]:
    """Node 2: Detect velocity spikes, stockout censoring, or OTIF delivery delays."""
    demand_service = DemandService()
    target_sku = state.get("target_sku_id")
    target_depot = state.get("target_depot_id")
    
    anomalies = []
    # If specific target provided, check that; otherwise scan critical SKU-depots
    scan_targets = [(target_sku, target_depot)] if (target_sku and target_depot) else [
        ("PR-DP", "Depot-West-01"),
        ("PR-PP", "Depot-North-01"),
        ("PR-MPB", "Depot-East-01"),
        ("PR-GC", "Depot-North-01"),
    ]
    
    for s_id, d_id in scan_targets:
        if not s_id or not d_id:
            continue
        corr = demand_service.detect_and_correct_censored_demand(s_id, d_id, lookback_days=7)
        if corr.get("is_censored") or (corr.get("demand_uplift_pct") and corr["demand_uplift_pct"] > 30.0):
            anomalies.append({
                "sku_id": s_id,
                "depot_id": d_id,
                "type": "DEMAND_SPIKE_OR_CENSORED",
                "uplift_pct": corr.get("demand_uplift_pct"),
                "adjustment_bottles": corr.get("censored_adjustment_sum"),
                "velocity": corr.get("unconstrained_daily_velocity"),
            })
            
    return {
        "anomalies_detected": anomalies,
        "status": "ANOMALIES_DETECTED",
    }


def node_diagnose_risk(state: DetectionState) -> Dict[str, Any]:
    """Node 3: Map detected anomalies to supply chain bottlenecks and Days of Cover impact."""
    inventory_service = InventoryService()
    risks = []
    for anom in state.get("anomalies_detected", []):
        s_id = anom["sku_id"]
        d_id = anom["depot_id"]
        vel = anom.get("velocity", 2000.0)
        inv = inventory_service.get_sku_depot_inventory_status(s_id, d_id, daily_forecast_demand=vel)
        doc = inv.get("days_of_cover", 0.0)
        gap = inv.get("allocation_gap", 0.0)
        
        risks.append({
            "sku_id": s_id,
            "depot_id": d_id,
            "days_of_cover": doc,
            "allocation_gap": gap,
            "is_critical": (doc is not None and doc < 7.0),
            "shelf_life_status": inv.get("shelf_life_status"),
        })
        
    return {
        "risks_diagnosed": risks,
        "status": "RISKS_DIAGNOSED",
    }


def node_forecast_demand(state: DetectionState) -> Dict[str, Any]:
    """Node 4: Apply demand sensing uplift to calculate forward corrected forecast."""
    forecasts = []
    for risk in state.get("risks_diagnosed", []):
        s_id = risk["sku_id"]
        d_id = risk["depot_id"]
        # Upward adjustment based on unconstrained velocity
        forecasts.append({
            "sku_id": s_id,
            "depot_id": d_id,
            "forward_target_cover_days": 21,
            "required_target_stock": risk["allocation_gap"],
        })
    return {
        "forecasts_adjusted": forecasts,
        "status": "FORECASTS_ADJUSTED",
    }


def node_evaluate_allocation(state: DetectionState) -> Dict[str, Any]:
    """Node 5: Check donor surplus availability and evaluate transfer feasibility."""
    dist_service = DistributionService()
    proposals = dist_service.optimize_inter_depot_rebalancing(
        sku_id=state.get("target_sku_id")
    )
    return {
        "allocation_evaluations": proposals,
        "status": "ALLOCATION_EVALUATED",
    }


def node_generate_recommendation(state: DetectionState) -> Dict[str, Any]:
    """Node 6: Format structured IBP exception tickets and persist as PENDING to recommendations.csv."""
    proposals = state.get("allocation_evaluations", [])
    recs_df = load_csv("recommendations")
    
    existing_ids = set(recs_df["recommendation_id"].astype(str)) if not recs_df.empty else set()
    persisted_recs = []

    for prop in proposals:
        rec_id = prop["recommendation_id"]
        if rec_id in existing_ids:
            continue
            
        record = {
            "recommendation_id": rec_id,
            "created_at": prop["created_at"],
            "priority": prop["priority"],
            "module": prop["module"],
            "sku_id": prop["sku_id"],
            "origin_depot_id": prop["origin_depot_id"],
            "destination_depot_id": prop["destination_depot_id"],
            "action_type": prop["action_type"],
            "quantity_bottles": prop["quantity_bottles"],
            "cost_inr": prop["cost_inr"],
            "protected_contribution_inr": prop["protected_contribution_inr"],
            "lead_time_days": prop["lead_time_days"],
            "eta_days": prop["eta_days"],
            "shelf_life_status": prop["shelf_life_status"],
            "donor_post_cover_days": prop["donor_post_cover_days"],
            "destination_post_cover_days": prop["destination_post_cover_days"],
            "shortage_reduction_bottles": prop["shortage_reduction_bottles"],
            "status": "PENDING",
            "confidence_level": prop["confidence_level"],
            "diagnosis": prop["diagnosis"],
            "is_synthetic": True,
        }
        append_csv_row("recommendations", record)
        persisted_recs.append(record)

    # Persist workflow state
    run_id = state.get("run_id", f"RUN-{uuid.uuid4().hex[:8]}")
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    workflow_entry = {
        "run_id": run_id,
        "timestamp": now_str,
        "pipeline_name": "DETECTION_PIPELINE",
        "step_name": "GENERATE_RECOMMENDATION",
        "status": "COMPLETED",
        "payload_json": json.dumps({
            "anomalies_count": len(state.get("anomalies_detected", [])),
            "recommendations_count": len(persisted_recs),
        }),
    }
    append_csv_row("workflow_state", workflow_entry)

    return {
        "recommendations_generated": persisted_recs,
        "status": "COMPLETED",
    }


def build_detection_graph() -> StateGraph:
    """Construct the compiled LangGraph StateGraph for detection pipeline."""
    builder = StateGraph(DetectionState)
    builder.add_node("ingest_signal", node_ingest_signal)
    builder.add_node("detect_anomaly", node_detect_anomaly)
    builder.add_node("diagnose_risk", node_diagnose_risk)
    builder.add_node("forecast_demand", node_forecast_demand)
    builder.add_node("evaluate_allocation", node_evaluate_allocation)
    builder.add_node("generate_recommendation", node_generate_recommendation)

    builder.set_entry_point("ingest_signal")
    builder.add_edge("ingest_signal", "detect_anomaly")
    builder.add_edge("detect_anomaly", "diagnose_risk")
    builder.add_edge("diagnose_risk", "forecast_demand")
    builder.add_edge("forecast_demand", "evaluate_allocation")
    builder.add_edge("evaluate_allocation", "generate_recommendation")
    builder.add_edge("generate_recommendation", END)

    return builder.compile()


def run_detection_pipeline(
    target_sku_id: Optional[str] = None,
    target_depot_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute the Phase 1 LangGraph detection pipeline.
    
    Returns the final workflow state including generated pending recommendations.
    """
    graph = build_detection_graph()
    initial_state: DetectionState = {
        "run_id": f"RUN-{datetime.datetime.now().strftime('%m%d%H%M%S')}",
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "target_sku_id": target_sku_id,
        "target_depot_id": target_depot_id,
        "signals_ingested_count": 0,
        "anomalies_detected": [],
        "risks_diagnosed": [],
        "forecasts_adjusted": [],
        "allocation_evaluations": [],
        "recommendations_generated": [],
        "status": "INITIALIZED",
        "error_message": None,
    }

    final_state = graph.invoke(initial_state)
    return dict(final_state)
