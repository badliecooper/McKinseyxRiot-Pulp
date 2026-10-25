"""Daily Sales Data Upload API for RIOT RADAR.

Provides:
- CSV & JSON upload endpoints for Modern Trade and Quick Commerce sales.
- Robust column alias mapping, date validation, SKU/Depot validation, and duplicate detection.
- Persistence to data/demand_history.csv and data/upload_history.csv.
- Automatic refresh of affected forecasts, inventory risk telemetry, and alarms.
- Transparent reporting of uploader, reporting period, ingestion timestamps, and synthetic data disclosures.
"""

import csv
import datetime
import io
import os
from typing import Dict, List, Optional, Any
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Body
from pydantic import BaseModel
import pandas as pd

import tools
from config.business_rules import SKUS, DEPOTS
from services.csv_store import load_csv, append_csv_row, save_csv

router = APIRouter(prefix="/upload", tags=["Data Ingestion"])

VALID_SKUS = set(SKUS.keys())
VALID_DEPOTS = {d["depot_id"] for d in DEPOTS}
DEPOT_NAME_MAP = {d["name"].lower(): d["depot_id"] for d in DEPOTS}
SKU_FLAVOUR_MAP = {s.flavour.lower(): s.sku_id for s in SKUS.values()}

CHANNEL_MAP = {
    "qc": "QC",
    "quick commerce": "QC",
    "mt": "MT",
    "modern trade": "MT",
    "gt": "GT",
    "general trade": "GT",
}


def normalize_sku(val: str) -> Optional[str]:
    clean = val.strip().upper()
    if clean in VALID_SKUS:
        return clean
    lower = val.strip().lower()
    if lower in SKU_FLAVOUR_MAP:
        return SKU_FLAVOUR_MAP[lower]
    return None


def normalize_depot(val: str) -> Optional[str]:
    clean = val.strip()
    if clean in VALID_DEPOTS:
        return clean
    lower = clean.lower()
    if lower in DEPOT_NAME_MAP:
        return DEPOT_NAME_MAP[lower]
    # Check partial city name match
    for d in DEPOTS:
        if d["region"].lower() in lower or d["name"].lower().split()[0] in lower:
            return d["depot_id"]
    return None


def normalize_channel(val: str) -> Optional[str]:
    lower = val.strip().lower()
    return CHANNEL_MAP.get(lower)


class SalesRecordInput(BaseModel):
    date: str
    sku_id: str
    depot_id: str
    channel: str
    observed_sales: float


class SalesUploadPayload(BaseModel):
    source: str = "Quick Commerce"
    uploader: str = "Central Planning Team"
    records: List[SalesRecordInput]


@router.get("/status")
def get_upload_status():
    """Retrieve metadata about the last successful data upload and data integrity notes."""
    upload_hist = load_csv("upload_history")
    last_record = None
    if not upload_hist.empty:
        last_record = upload_hist.iloc[-1].to_dict()

    return {
        "status": "ONLINE",
        "last_upload": last_record,
        "supported_channels": ["Modern Trade (MT)", "Quick Commerce (QC)", "General Trade (GT)"],
        "data_honesty_badge": (
            "Note: Lot-level shelf-life distribution and baseline ground-truth series are synthetic demo constructs "
            "calibrated to case constraints. Daily uploaded sales are validated and persisted to local CSV demand store."
        ),
        "retailer_integration_status": (
            "Offline / Portal Upload. No automated live EDI/API link with Blinkit, Zepto, or DMart dark stores. "
            "Files are ingested via validated daily partner CSV feeds."
        ),
    }


@router.post("/sales")
async def upload_sales_csv(
    file: Optional[UploadFile] = File(None),
    source_channel: str = Form("Quick Commerce"),
    uploader_name: str = Form("Planning Team"),
):
    """Upload and validate CSV daily sales for MT or QC channels."""
    if not file:
        raise HTTPException(status_code=400, detail="No file provided. Please attach a CSV file.")

    contents = await file.read()
    try:
        text = contents.decode("utf-8")
    except UnicodeDecodeError:
        text = contents.decode("latin-1")

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise HTTPException(status_code=400, detail="Uploaded CSV file is empty or missing headers.")

    # Column header mapping
    header_map = {}
    for h in reader.fieldnames:
        hl = h.strip().lower().replace(" ", "_")
        if hl in ["date", "day", "sales_date", "timestamp"]:
            header_map["date"] = h
        elif hl in ["sku_id", "sku", "product_id", "flavor", "flavour"]:
            header_map["sku_id"] = h
        elif hl in ["depot_id", "depot", "warehouse", "location"]:
            header_map["depot_id"] = h
        elif hl in ["channel", "sales_channel"]:
            header_map["channel"] = h
        elif hl in ["observed_sales", "sales", "quantity", "qty", "volume", "bottles"]:
            header_map["observed_sales"] = h

    missing = [req for req in ["date", "sku_id", "depot_id", "observed_sales"] if req not in header_map]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Missing required columns in CSV: {', '.join(missing)}. Recognized headers: date, sku_id, depot_id, channel, observed_sales.",
        )

    # Validate existing records to detect duplicates
    demand_df = load_csv("demand_history")
    existing_keys = set()
    if not demand_df.empty:
        for _, r in demand_df.iterrows():
            key = (str(r["date"]).strip(), str(r["sku_id"]).strip(), str(r["depot_id"]).strip(), str(r["channel"]).strip().upper())
            existing_keys.add(key)

    valid_rows = []
    errors = []
    skipped_duplicates = 0
    dates_seen = []

    row_num = 1
    for row in reader:
        row_num += 1
        raw_date = row.get(header_map["date"], "").strip()
        raw_sku = row.get(header_map["sku_id"], "").strip()
        raw_depot = row.get(header_map["depot_id"], "").strip()
        raw_channel = row.get(header_map.get("channel", ""), "").strip() or source_channel
        raw_sales = row.get(header_map["observed_sales"], "").strip()

        # Date validation
        try:
            parsed_date = datetime.datetime.strptime(raw_date, "%Y-%m-%d").date()
            date_str = parsed_date.strftime("%Y-%m-%d")
            dates_seen.append(date_str)
        except ValueError:
            errors.append(f"Row {row_num}: Invalid date format '{raw_date}'. Expected YYYY-MM-DD.")
            continue

        # SKU validation
        norm_sku = normalize_sku(raw_sku)
        if not norm_sku:
            errors.append(f"Row {row_num}: Unknown SKU '{raw_sku}'. Must be one of: {', '.join(sorted(VALID_SKUS))}.")
            continue

        # Depot validation
        norm_depot = normalize_depot(raw_depot)
        if not norm_depot:
            errors.append(f"Row {row_num}: Unknown Depot '{raw_depot}'. Must be one of: {', '.join(sorted(VALID_DEPOTS))}.")
            continue

        # Channel normalization
        norm_channel = normalize_channel(raw_channel) or ("QC" if "quick" in source_channel.lower() else "MT")

        # Sales quantity validation
        try:
            sales_val = float(raw_sales)
            if sales_val < 0:
                errors.append(f"Row {row_num}: Negative sales value '{raw_sales}'.")
                continue
        except ValueError:
            errors.append(f"Row {row_num}: Invalid numeric sales value '{raw_sales}'.")
            continue

        # Duplicate check
        composite_key = (date_str, norm_sku, norm_depot, norm_channel)
        if composite_key in existing_keys:
            skipped_duplicates += 1
            continue

        # New valid row
        source_type = "qc_daily_sell_through" if norm_channel == "QC" else "mt_sell_through" if norm_channel == "MT" else "distributor_orders"
        freshness_lag = 1 if norm_channel == "QC" else 2 if norm_channel == "MT" else 7

        record = {
            "date": date_str,
            "sku_id": norm_sku,
            "depot_id": norm_depot,
            "channel": norm_channel,
            "observed_sales": int(sales_val),
            "source_type": source_type,
            "freshness_lag_days": freshness_lag,
            "is_stockout_flagged": False,
            "censored_adjustment": 0,
            "corrected_demand": int(sales_val),
            "is_synthetic": False,  # Real user upload!
        }
        valid_rows.append(record)
        existing_keys.add(composite_key)

    if errors and len(errors) > 10:
        return {
            "status": "VALIDATION_FAILED",
            "message": f"Found {len(errors)} validation errors. Ingestion aborted.",
            "errors": errors[:15],
            "total_errors": len(errors),
        }

    if not valid_rows and skipped_duplicates > 0:
        return {
            "status": "ALL_DUPLICATES",
            "message": f"All {skipped_duplicates} rows in file already exist in demand_history.csv. No changes made.",
            "duplicates_skipped": skipped_duplicates,
        }

    if not valid_rows:
        raise HTTPException(
            status_code=400,
            detail=f"No valid records found to ingest. Errors: {'; '.join(errors[:5])}",
        )

    # Persist valid rows to demand_history.csv
    for r in valid_rows:
        append_csv_row("demand_history", r)

    # Persist upload metadata to upload_history.csv
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    upload_id = f"UPL-{datetime.datetime.now().strftime('%m%d%H%M')}-{len(valid_rows):03d}"
    min_date = min(dates_seen) if dates_seen else "N/A"
    max_date = max(dates_seen) if dates_seen else "N/A"
    reporting_period = f"{min_date} to {max_date}"

    upload_meta = {
        "upload_id": upload_id,
        "uploaded_at": now_str,
        "uploader": uploader_name,
        "source_channel": source_channel,
        "reporting_period": reporting_period,
        "records_processed": row_num - 1,
        "records_inserted": len(valid_rows),
        "duplicates_skipped": skipped_duplicates,
        "errors_count": len(errors),
    }

    # Ensure upload_history table exists and append
    hist_df = load_csv("upload_history")
    if hist_df.empty:
        new_df = pd.DataFrame([upload_meta])
        save_csv("upload_history", new_df)
    else:
        append_csv_row("upload_history", upload_meta)

    # Trigger alarm evaluation and telemetry sync
    tools._risk_svc.evaluate_and_sync_alarms()

    return {
        "status": "SUCCESS",
        "upload_id": upload_id,
        "message": f"Successfully ingested {len(valid_rows):,} sales records into demand_history.csv.",
        "uploader": uploader_name,
        "source_channel": source_channel,
        "reporting_period": reporting_period,
        "records_inserted": len(valid_rows),
        "duplicates_skipped": skipped_duplicates,
        "timestamp": now_str,
        "warnings": errors[:5] if errors else [],
    }
