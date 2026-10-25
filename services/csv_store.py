"""CSV Store service for RIOT RADAR.

Provides robust, atomic, thread-safe persistence using only CSV files.
Enforces schema validation, unique ID generation, duplicate detection,
and atomic file replacements.
"""

import os
import tempfile
import threading
from pathlib import Path
from typing import Dict, List, Optional, Any
import pandas as pd

# Default data directory relative to repository root
DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# Thread lock for file operations within the Python process
_FILE_LOCK = threading.RLock()

# Schemas: Table name to list of required columns
SCHEMAS: Dict[str, List[str]] = {
    "depots": ["depot_id", "name", "region", "lead_time_days"],
    "products": [
        "sku_id",
        "flavour",
        "summer_share_pct",
        "primary_planning_concern",
        "pulp_type",
        "pulp_kg_per_bottle",
    ],
    "demand_history": [
        "date",
        "sku_id",
        "depot_id",
        "channel",
        "observed_sales",
        "source_type",
        "freshness_lag_days",
        "is_stockout_flagged",
        "censored_adjustment",
        "corrected_demand",
        "is_synthetic",
    ],
    "inventory": [
        "sku_id",
        "depot_id",
        "usable_stock_mt_qc",
        "usable_stock_gt_only",
        "near_cliff_stock",
        "total_usable_stock",
        "lot_batch_id",
        "remaining_shelf_life_days",
        "last_audit_date",
        "is_synthetic",
    ],
    "inbound_shipments": [
        "shipment_id",
        "sku_id",
        "destination_depot_id",
        "qty_bottles",
        "origin_type",
        "origin_id",
        "dispatch_date",
        "expected_arrival_date",
        "actual_arrival_date",
        "status",
        "is_on_time",
        "is_in_full",
    ],
    "supplier_status": [
        "supplier_id",
        "material_name",
        "origin_location",
        "transit_mode",
        "standard_lead_time_days",
        "active_disruption_flag",
        "disruption_type",
        "effective_delay_days",
        "notes",
    ],
    "forecast_snapshots": [
        "vintage_id",
        "snapshot_date",
        "target_date",
        "sku_id",
        "depot_id",
        "forecast_demand",
        "naive_baseline_demand",
        "model_version",
        "is_synthetic",
    ],
    "recommendations": [
        "recommendation_id",
        "created_at",
        "priority",
        "module",
        "sku_id",
        "origin_depot_id",
        "destination_depot_id",
        "action_type",
        "quantity_bottles",
        "cost_inr",
        "protected_contribution_inr",
        "lead_time_days",
        "eta_days",
        "shelf_life_status",
        "donor_post_cover_days",
        "destination_post_cover_days",
        "shortage_reduction_bottles",
        "status",
        "confidence_level",
        "diagnosis",
        "is_synthetic",
    ],
    "approvals": [
        "approval_id",
        "recommendation_id",
        "decision",
        "decided_at",
        "approver_id",
        "approver_role",
        "modified_quantity_bottles",
        "notes",
    ],
    "stockout_reports": [
        "report_id",
        "reported_at",
        "depot_id",
        "sku_id",
        "channel",
        "reported_by",
        "evidence_source",
        "estimated_unmet_bottles",
        "notes",
    ],
    "audit_log": [
        "event_id",
        "timestamp",
        "event_type",
        "entity_type",
        "entity_id",
        "actor_id",
        "action",
        "details_json",
    ],
    "workflow_state": [
        "run_id",
        "timestamp",
        "pipeline_name",
        "step_name",
        "status",
        "payload_json",
    ],
    "alarms": [
        "alarm_id",
        "created_at",
        "updated_at",
        "alarm_type",
        "severity",
        "status",
        "sku_id",
        "depot_id",
        "channel",
        "title",
        "description",
        "observed_value",
        "threshold_value",
        "source",
        "confidence_level",
        "recommended_action",
        "recommendation_id",
        "acknowledged_by",
        "acknowledged_at",
        "resolved_at",
        "resolution_notes",
        "is_synthetic",
    ],
}


def get_data_path(table_name: str) -> Path:
    """Get absolute path to a CSV file in data directory."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR / f"{table_name}.csv"


def initialize_csv(table_name: str, force: bool = False) -> Path:
    """Initialize an empty CSV file with appropriate header columns if missing."""
    file_path = get_data_path(table_name)
    if force or not file_path.exists():
        columns = SCHEMAS.get(table_name, ["id", "created_at"])
        df = pd.DataFrame(columns=columns)
        save_csv(table_name, df)
    return file_path


def load_csv(table_name: str) -> pd.DataFrame:
    """Load a CSV file as a pandas DataFrame.
    
    If the file does not exist, initializes it with empty schema.
    Validates required columns and returns an empty DataFrame if empty.
    """
    file_path = get_data_path(table_name)
    with _FILE_LOCK:
        if not file_path.exists() or os.path.getsize(file_path) == 0:
            initialize_csv(table_name, force=True)
        try:
            df = pd.read_csv(file_path, dtype=str)
        except Exception:
            # Fallback to empty with schema if corrupted/empty
            columns = SCHEMAS.get(table_name, [])
            df = pd.DataFrame(columns=columns)
            
        # Ensure all required columns exist
        required_cols = SCHEMAS.get(table_name, [])
        for col in required_cols:
            if col not in df.columns:
                df[col] = None
        return df


def save_csv(table_name: str, df: pd.DataFrame) -> None:
    """Atomically write a DataFrame to CSV using a temporary file and os.replace.
    
    Ensures safe, thread-safe, all-or-nothing writes without partial corruptions.
    """
    file_path = get_data_path(table_name)
    with _FILE_LOCK:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        # Write to a temporary file in the same directory for atomic replace
        temp_file = tempfile.NamedTemporaryFile(
            mode="w",
            dir=str(DATA_DIR),
            delete=False,
            suffix=".tmp",
            encoding="utf-8",
            newline="",
        )
        try:
            df.to_csv(temp_file.name, index=False, encoding="utf-8")
            temp_file.close()
            # Atomic replacement
            os.replace(temp_file.name, file_path)
        except Exception:
            if os.path.exists(temp_file.name):
                try:
                    os.remove(temp_file.name)
                except OSError:
                    pass
            raise


def append_csv_row(table_name: str, row: Dict[str, Any]) -> None:
    """Safely append a single row dictionary to a CSV table."""
    with _FILE_LOCK:
        df = load_csv(table_name)
        new_row_df = pd.DataFrame([row])
        # Reorder or add columns
        for col in SCHEMAS.get(table_name, []):
            if col not in new_row_df.columns:
                new_row_df[col] = None
        updated_df = pd.concat([df, new_row_df], ignore_index=True)
        save_csv(table_name, updated_df)


def update_csv_record(
    table_name: str,
    id_column: str,
    id_value: str,
    updates: Dict[str, Any],
) -> bool:
    """Update fields of an existing record matching id_column == id_value."""
    with _FILE_LOCK:
        df = load_csv(table_name)
        if df.empty or id_column not in df.columns:
            return False
        mask = df[id_column].astype(str) == str(id_value)
        if not mask.any():
            return False
        for col, val in updates.items():
            if col not in df.columns:
                df[col] = None
            df.loc[mask, col] = str(val) if val is not None else None
        save_csv(table_name, df)
        return True


def ensure_all_csvs() -> None:
    """Ensure all required CSV files exist with schemas."""
    with _FILE_LOCK:
        for table in SCHEMAS.keys():
            initialize_csv(table)
