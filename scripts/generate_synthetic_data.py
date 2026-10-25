#!/usr/bin/env python3
"""Full 4-Month Summer Synthetic Dataset Generator for RIOT RADAR.

Populates the entire 4-month peak summer quarter (2026-03-01 to 2026-06-30, 122 days)
across all 14 CSV files in the data directory with exact McKinsey / Transfinitte PS1 calibration:
- 45 SKU–Depot combinations (9 Depots x 5 SKUs).
- 5,490 daily demand history rows.
- 765 forecast snapshot rows (17 weekly vintages x 45 cells, zero look-ahead leakage).
- Exactly 9.60 Cr bottles corrected demand (₹576.00 Cr at ₹60/bottle).
- Exactly 0.768 Cr bottles stock-out censored volume (8.00% = ₹46.08 Cr lost revenue).
- Exactly 8.832 Cr bottles observed sales (₹529.92 Cr realized revenue).
- Four-month chronological progression: March viral QC spike, April regional drift,
  May highway closure & raw pulp scarcity, June co-packer & rebalancing stabilization.
- Atomic writes and strict idempotency.
"""

import os
import shutil
import tempfile
import argparse
import sys
import datetime
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional

# Ensure UTF-8 stdout/stderr on Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import numpy as np
import pandas as pd

# Add repo root to path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from config.business_rules import (
    SKUS,
    DEPOTS,
    CHANNEL_MIX,
    DEFAULT_TARGET_COVER_DAYS,
    TRANSFER_COST_PER_BOTTLE_INR,
    NEAR_CLIFF_WARNING_DAYS,
    MT_QC_MIN_SHELF_LIFE_DAYS,
    SUMMER_VOLUME_BOTTLES,
    HISTORICAL_STOCKOUT_LOST_REVENUE_INR_CR,
    BOTTLE_PRICE_INR,
    CONTRIBUTION_MARGIN_PCT,
)


def get_cli_parser() -> argparse.ArgumentParser:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Full 4-Month Summer Synthetic Dataset Generator for RIOT RADAR."
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default=str(REPO_ROOT / "data"),
        help="Target directory for CSV files (default: data/)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducibility (default: 42)",
    )
    parser.add_argument(
        "--start-date",
        type=str,
        default="2026-03-01",
        help="Start date of summer quarter YYYY-MM-DD (default: 2026-03-01)",
    )
    parser.add_argument(
        "--end-date",
        type=str,
        default="2026-06-30",
        help="End date of summer quarter YYYY-MM-DD (default: 2026-06-30)",
    )
    parser.add_argument(
        "--backup-dir",
        type=str,
        default=str(REPO_ROOT / ".backups" / "csv_seed_backup"),
        help="Backup directory before writes (default: .backups/csv_seed_backup)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Compute and validate all metrics without modifying CSV files on disk.",
    )
    return parser


def backup_existing_csvs(data_dir: Path, backup_dir: Path) -> int:
    """Backup all existing CSV files in data_dir to backup_dir."""
    backup_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    for csv_file in data_dir.glob("*.csv"):
        dest = backup_dir / csv_file.name
        shutil.copy2(csv_file, dest)
        count += 1
    return count


def atomic_save_csv(file_path: Path, df: pd.DataFrame) -> None:
    """Atomically write DataFrame to CSV using a temporary file in the destination folder."""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(
        dir=str(file_path.parent),
        prefix="tmp_" + file_path.stem + "_",
        suffix=".csv",
    )
    try:
        with os.fdopen(fd, "w", newline="", encoding="utf-8") as f:
            df.to_csv(f, index=False)
        os.replace(temp_path, file_path)
    except Exception:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise


# ==============================================================================
# 1. DEPOTS & 2. PRODUCTS
# ==============================================================================
def generate_depots() -> pd.DataFrame:
    """Generate exact 9 depots across 5 regions."""
    return pd.DataFrame(DEPOTS)


def generate_products() -> pd.DataFrame:
    """Generate exact 5 SKUs with summer share percentages summing to 100.0."""
    products_data = []
    for sku_id, sku in SKUS.items():
        products_data.append({
            "sku_id": sku.sku_id,
            "flavour": sku.flavour,
            "summer_share_pct": float(sku.summer_share_pct),
            "primary_planning_concern": sku.primary_planning_concern,
            "pulp_type": sku.pulp_type,
            "pulp_kg_per_bottle": float(sku.pulp_kg_per_bottle),
        })
    df = pd.DataFrame(products_data)
    assert abs(df["summer_share_pct"].sum() - 100.0) < 1e-4, "SKU summer shares must sum to 100.0%!"
    return df


# ==============================================================================
# 3. DEMAND HISTORY (5,490 ROWS, 122 DAYS, EXACT CALIBRATION)
# ==============================================================================
def generate_demand_history(
    start_date_str: str = "2026-03-01",
    end_date_str: str = "2026-06-30",
    seed: int = 42,
) -> pd.DataFrame:
    """Generate exact 5,490 demand history rows for 45 SKU-depots across 122 days.
    
    Reconciles with case figures:
    - Total corrected demand: 96,000,000 bottles (₹576.00 Cr)
    - Total stock-out censored volume: 7,680,000 bottles (8.00% = ₹46.08 Cr lost revenue)
    - Total observed sales: 88,320,000 bottles (₹529.92 Cr)
    - Strict row identity: corrected_demand == observed_sales + censored_adjustment
    """
    rng = np.random.RandomState(seed)

    start_date = datetime.date.fromisoformat(start_date_str)
    end_date = datetime.date.fromisoformat(end_date_str)
    days_count = (end_date - start_date).days + 1
    assert days_count == 122, f"Expected 122 days for summer quarter, got {days_count}"

    dates = [start_date + datetime.timedelta(days=i) for i in range(days_count)]

    # SKU Summer Volumes (Exactly 96.0 Cr bottles total)
    sku_targets = {
        "PR-MPB": 36_480_000,  # 38.0%
        "PR-GC": 19_200_000,   # 20.0%
        "PR-PP": 15_360_000,   # 16.0%
        "PR-DB": 13_440_000,   # 14.0%
        "PR-DP": 11_520_000,   # 12.0%
    }

    # Baseline Regional Depot Weights
    depot_weights = {
        "Depot-North-01": 0.20,  # Delhi NCR
        "Depot-North-02": 0.08,  # Lucknow
        "Depot-West-01": 0.22,   # Mumbai
        "Depot-West-02": 0.10,   # Ahmedabad
        "Depot-South-01": 0.16,  # Bengaluru
        "Depot-South-02": 0.09,  # Chennai
        "Depot-East-01": 0.07,   # Kolkata
        "Depot-East-02": 0.03,   # Guwahati
        "Depot-Central-01": 0.05,# Indore
    }

    raw_records = []

    # Channel rotation pattern: 11 GT (55%), 5 MT (25%), 4 QC (20%)
    channel_cycle = ["GT"] * 11 + ["MT"] * 5 + ["QC"] * 4

    row_idx = 0
    for t, d in enumerate(dates):
        d_str = d.strftime("%Y-%m-%d")
        month = d.month
        day_of_month = d.day
        is_weekend = d.weekday() >= 5
        dow_mult = 1.08 if is_weekend else 0.97

        # Seasonal temperature curve: March ramping into peak May heat, softening mid-June
        season_mult = 0.85 + (t / 121.0) * 0.32
        if month == 6 and day_of_month > 15:
            season_mult -= 0.10

        for sku_id, target_tot in sku_targets.items():
            for depot_id, base_dw in depot_weights.items():
                dw = base_dw
                viral_mult = 1.0
                is_qc_viral = False

                # 1. March Viral Spike for PR-DP (2026-03-15 to 2026-03-28)
                if sku_id == "PR-DP" and datetime.date(2026, 3, 15) <= d <= datetime.date(2026, 3, 28):
                    if depot_id in ["Depot-West-01", "Depot-North-01"]:
                        viral_mult = 4.0
                        is_qc_viral = True
                    elif depot_id == "Depot-South-01":
                        viral_mult = 1.65
                        is_qc_viral = True

                # 2. April Regional Drift for PR-GC and PR-MPB (Summer heat migration)
                drift_mult = 1.0
                if month == 4 and sku_id in ["PR-GC", "PR-MPB"]:
                    if "North" in depot_id or "West" in depot_id:
                        drift_mult = 1.25
                    elif "East" in depot_id or "Central" in depot_id:
                        drift_mult = 0.70

                noise = rng.normal(1.0, 0.04)
                raw_w = target_tot * dw * season_mult * dow_mult * viral_mult * drift_mult * noise

                # 3. Stock-Out Censoring Ratios:
                censored_ratio = 0.0

                # 1. March Viral Spike Stock-Outs on PR-DP (Mumbai, Delhi, Bengaluru)
                if sku_id == "PR-DP" and depot_id in ["Depot-West-01", "Depot-North-01", "Depot-South-01"] and datetime.date(2026, 3, 20) <= d <= datetime.date(2026, 4, 10):
                    censored_ratio = 0.85
                # 2. April Regional Drift Deficits on PR-GC & PR-MPB (Northern and Western heat wave)
                elif sku_id in ["PR-GC", "PR-MPB"] and ("North" in depot_id or "West" in depot_id) and datetime.date(2026, 4, 1) <= d <= datetime.date(2026, 4, 30):
                    censored_ratio = 0.45
                # 3. May Passionfruit Highway Disruption: cuts pulp supply for PR-PP & PR-DP across network
                elif sku_id in ["PR-PP", "PR-DP"] and datetime.date(2026, 5, 8) <= d <= datetime.date(2026, 5, 31):
                    censored_ratio = 0.65
                # 4. May Dragonfruit Maritime Import Delay on PR-DB (West, South, Central)
                elif sku_id == "PR-DB" and depot_id in ["Depot-West-01", "Depot-South-01", "Depot-Central-01"] and datetime.date(2026, 5, 12) <= d <= datetime.date(2026, 6, 5):
                    censored_ratio = 0.40
                # 5. Late June Rebalancing Transit Lags on PR-DP & PR-GC (Depot-West-01, Depot-North-01)
                elif sku_id in ["PR-DP", "PR-GC"] and depot_id in ["Depot-West-01", "Depot-North-01"] and datetime.date(2026, 6, 15) <= d <= datetime.date(2026, 6, 30):
                    censored_ratio = 0.35

                # Channel Assignment
                if is_qc_viral:
                    channel = "QC"
                    source_type = "qc_daily_sell_through"
                    freshness_lag = 1
                else:
                    channel = channel_cycle[row_idx % len(channel_cycle)]
                    if channel == "QC":
                        source_type = "qc_daily_sell_through"
                        freshness_lag = 1
                    elif channel == "MT":
                        source_type = "distributor_orders"
                        freshness_lag = 5
                    else:
                        source_type = "distributor_orders"
                        freshness_lag = 7

                raw_records.append({
                    "date": d_str,
                    "sku_id": sku_id,
                    "depot_id": depot_id,
                    "channel": channel,
                    "source_type": source_type,
                    "freshness_lag_days": freshness_lag,
                    "raw_w": max(10.0, raw_w),
                    "censored_ratio": censored_ratio,
                    "is_synthetic": True,
                })
                row_idx += 1

    df = pd.DataFrame(raw_records)
    assert len(df) == 5490, f"Expected 5,490 rows, got {len(df)}"

    # Exact calibration: scale each SKU to match sku_targets exactly
    df["corrected_demand"] = 0
    for sku_id, target in sku_targets.items():
        mask = df["sku_id"] == sku_id
        sub_raw = df.loc[mask, "raw_w"]
        scaled = (sub_raw / sub_raw.sum()) * target
        int_scaled = np.round(scaled).astype(int)
        diff = target - int_scaled.sum()
        int_scaled.iloc[int_scaled.argmax()] += diff
        df.loc[mask, "corrected_demand"] = int_scaled

    # Exact calibration of stock-out censored volume to 7,680,000 bottles (8.00%)
    df["raw_censored"] = df["corrected_demand"] * df["censored_ratio"]
    cens_mask = df["raw_censored"] > 0
    target_cens = 7_680_000
    scale_cens = target_cens / df.loc[cens_mask, "raw_censored"].sum()
    int_cens = np.round(df.loc[cens_mask, "raw_censored"] * scale_cens).astype(int)
    diff_cens = target_cens - int_cens.sum()
    int_cens.iloc[int_cens.argmax()] += diff_cens

    df["censored_adjustment"] = 0
    df.loc[cens_mask, "censored_adjustment"] = int_cens
    df["observed_sales"] = df["corrected_demand"] - df["censored_adjustment"]
    df["is_stockout_flagged"] = df["censored_adjustment"] > 0

    # Ensure zero negative values and strict physical bounds
    assert (df["observed_sales"] >= 0).all(), "Observed sales must never be negative!"
    assert (df["censored_adjustment"] >= 0).all(), "Censored adjustment must never be negative!"
    assert (df["observed_sales"] <= df["corrected_demand"]).all(), "Observed sales cannot exceed corrected demand!"

    # Ensure clean final columns
    cols = [
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
    ]
    df = df[cols]

    # Verification assertions
    assert df["corrected_demand"].sum() == 96_000_000, "Total corrected demand must equal 96,000,000"
    assert df["censored_adjustment"].sum() == 7_680_000, "Total censored volume must equal 7,680,000"
    assert df["observed_sales"].sum() == 88_320_000, "Total observed sales must equal 88,320,000"
    assert (df["corrected_demand"] == df["observed_sales"] + df["censored_adjustment"]).all()
    assert (df["is_stockout_flagged"] == (df["censored_adjustment"] > 0)).all()

    return df


# ==============================================================================
# 4. FORECAST SNAPSHOTS (765 ROWS, 17 WEEKLY VINTAGES, ZERO LEAKAGE)
# ==============================================================================
def generate_forecast_snapshots(
    demand_df: pd.DataFrame,
    seed: int = 42,
) -> pd.DataFrame:
    """Generate 765 forecast snapshot rows (17 weekly vintages x 45 cells).
    
    Zero Look-Ahead Leakage: Every row satisfies snapshot_date < target_date (7d lead).
    Places VINTAGE-2026-W18 (snapshot_date=2026-05-13, target_date=2026-05-20) first in the file.
    """
    rng = np.random.RandomState(seed)

    # 17 weekly vintages from W09 to W25
    # Reference anchor: W18 target_date is 2026-05-20, snapshot_date is 2026-05-13
    w18_target = datetime.date(2026, 5, 20)
    vintage_defs = []
    for w in range(9, 26):
        target_d = w18_target + datetime.timedelta(weeks=(w - 18))
        snapshot_d = target_d - datetime.timedelta(days=7)
        vintage_defs.append((f"VINTAGE-2026-W{w:02d}", snapshot_d.strftime("%Y-%m-%d"), target_d.strftime("%Y-%m-%d")))

    # Calculate average daily actual demand per SKU-depot to anchor realistic forecasts
    avg_demand = demand_df.groupby(["sku_id", "depot_id"])["corrected_demand"].mean().to_dict()

    # Pre-compute tailored bias profiles for W18 to reconcile with the 10.7% WAPE and -1.8% bias
    # while demonstrating the Aggregation Fallacy (cancelling errors):
    w18_records = []
    w18_v_id, w18_snap, w18_target_str = vintage_defs[9]  # index 9 is W18
    assert w18_v_id == "VINTAGE-2026-W18"

    for sku_id, sku in SKUS.items():
        for depot in DEPOTS:
            depot_id = depot["depot_id"]
            d_mean = avg_demand.get((sku_id, depot_id), 17500.0)

            # Tailor bias profile
            if sku_id == "PR-DP" and depot_id in ["Depot-West-01", "Depot-North-01"]:
                bias = -0.184  # Under-forecast viral surge
                naive_bias = -0.320
            elif sku_id == "PR-MPB" and depot_id in ["Depot-East-01", "Depot-Central-01"]:
                bias = +0.162  # Over-forecast slowing region
                naive_bias = +0.280
            elif sku_id == "PR-GC" and depot_id == "Depot-North-01":
                bias = -0.145
                naive_bias = -0.250
            elif sku_id == "PR-PP" and "North" in depot_id:
                bias = -0.110
                naive_bias = -0.220
            else:
                noise = rng.normal(-0.015, 0.07)
                bias = noise
                naive_bias = noise * 1.8

            f_daily = round(d_mean * (1.0 + bias))
            n_daily = round(d_mean * (1.0 + naive_bias))

            w18_records.append({
                "vintage_id": w18_v_id,
                "snapshot_date": w18_snap,
                "target_date": w18_target_str,
                "sku_id": sku_id,
                "depot_id": depot_id,
                "forecast_demand": max(100, f_daily),
                "naive_baseline_demand": max(100, n_daily),
                "model_version": "Sensing-v1.4",
                "is_synthetic": True,
            })

    # Generate other vintages
    other_records = []
    for v_id, snap_str, targ_str in vintage_defs:
        if v_id == "VINTAGE-2026-W18":
            continue  # Already generated for the top of the file

        w_num = int(v_id.split("-W")[1])
        model_ver = "Sensing-v1.2" if w_num < 14 else ("Sensing-v1.3" if w_num < 18 else "Sensing-v1.4")

        for sku_id, sku in SKUS.items():
            for depot in DEPOTS:
                depot_id = depot["depot_id"]
                d_mean = avg_demand.get((sku_id, depot_id), 17500.0)

                # Early vintages had higher error before model sensing ramped up
                error_scale = 0.16 if w_num < 14 else (0.12 if w_num < 18 else 0.09)
                bias = rng.normal(-0.02, error_scale)
                naive_bias = rng.normal(0.01, 0.22)

                f_daily = round(d_mean * (1.0 + bias))
                n_daily = round(d_mean * (1.0 + naive_bias))

                other_records.append({
                    "vintage_id": v_id,
                    "snapshot_date": snap_str,
                    "target_date": targ_str,
                    "sku_id": sku_id,
                    "depot_id": depot_id,
                    "forecast_demand": max(100, f_daily),
                    "naive_baseline_demand": max(100, n_daily),
                    "model_version": model_ver,
                    "is_synthetic": True,
                })

    # Strict rule: Place VINTAGE-2026-W18 first
    all_forecasts = w18_records + other_records
    df = pd.DataFrame(all_forecasts)

    assert len(df) == 765, f"Expected 765 forecast rows (17 vintages x 45 cells), got {len(df)}"
    # Strict look-ahead check
    assert (df["snapshot_date"] < df["target_date"]).all(), "Look-ahead violation detected in forecast snapshots!"
    assert df.iloc[0]["vintage_id"] == "VINTAGE-2026-W18", "VINTAGE-2026-W18 must be first!"

    return df


# ==============================================================================
# 5. INVENTORY (45 ROWS, STRICT IDENTITY, CHANNEL SEGMENTATION)
# ==============================================================================
def generate_inventory(demand_df: pd.DataFrame) -> pd.DataFrame:
    """Generate 45 inventory rows matching the 45 SKU-depots with strict channel identity."""
    avg_demand = demand_df.groupby(["sku_id", "depot_id"])["corrected_demand"].mean().to_dict()

    inv_records = []
    base_audit_date = "2026-05-20"

    for sku_id, sku in SKUS.items():
        for depot in DEPOTS:
            depot_id = depot["depot_id"]
            d_mean = avg_demand.get((sku_id, depot_id), 17500.0)

            # Case facts and specific conditions:
            if sku_id == "PR-DP" and depot_id == "Depot-West-01":
                # Critical stockout / low cover: 3.5 days of cover
                total_usable = round(d_mean * 3.5)
                usable_mt_qc = round(total_usable * 0.90)
                usable_gt_only = total_usable - usable_mt_qc
                near_cliff = 0
                shelf_days = 72
            elif sku_id == "PR-DP" and depot_id == "Depot-South-02":
                # Surplus donor: 32 days of cover
                total_usable = round(d_mean * 32.0)
                usable_mt_qc = round(total_usable * 0.85)
                usable_gt_only = total_usable - usable_mt_qc
                near_cliff = round(total_usable * 0.05)
                shelf_days = 76
            elif sku_id == "PR-MPB" and depot_id in ["Depot-East-01", "Depot-Central-01"]:
                # High volume excess stock approaching shelf-life cliff (60-67d window)
                total_usable = round(d_mean * 28.0)
                near_cliff = round(total_usable * 0.35)  # 35% near-cliff!
                usable_gt_only = round(total_usable * 0.20)
                usable_mt_qc = total_usable - usable_gt_only
                shelf_days = 63  # Near-cliff gate trigger!
            elif sku_id == "PR-GC" and depot_id == "Depot-North-01":
                # Shortage at North-01: 9.0 days cover
                total_usable = round(d_mean * 9.0)
                usable_mt_qc = round(total_usable * 0.85)
                usable_gt_only = total_usable - usable_mt_qc
                near_cliff = 0
                shelf_days = 78
            elif sku_id == "PR-GC" and depot_id in ["Depot-South-01", "Depot-West-02"]:
                # Surplus at South-01: 29.0 days cover
                total_usable = round(d_mean * 29.0)
                usable_mt_qc = round(total_usable * 0.90)
                usable_gt_only = total_usable - usable_mt_qc
                near_cliff = round(total_usable * 0.08)
                shelf_days = 75
            elif sku_id == "PR-PP" and depot_id == "Depot-North-01":
                # Shortage due to highway closure: 5.5 days cover
                total_usable = round(d_mean * 5.5)
                usable_mt_qc = round(total_usable * 0.80)
                usable_gt_only = total_usable - usable_mt_qc
                near_cliff = 0
                shelf_days = 74
            else:
                # Balanced healthy cover: 19 - 24 days
                doc = 19.5 + (hash(f"{sku_id}_{depot_id}") % 50) / 10.0
                total_usable = round(d_mean * doc)
                usable_mt_qc = round(total_usable * 0.85)
                usable_gt_only = total_usable - usable_mt_qc
                near_cliff = round(total_usable * 0.05)
                shelf_days = 72 + int(hash(f"{sku_id}_{depot_id}") % 12)

            lot_id = f"LOT-{sku_id}-{depot_id[:7]}-B01"

            inv_records.append({
                "sku_id": sku_id,
                "depot_id": depot_id,
                "usable_stock_mt_qc": usable_mt_qc,
                "usable_stock_gt_only": usable_gt_only,
                "near_cliff_stock": near_cliff,
                "total_usable_stock": total_usable,
                "lot_batch_id": lot_id,
                "remaining_shelf_life_days": shelf_days,
                "last_audit_date": base_audit_date,
                "is_synthetic": True,
            })

    df = pd.DataFrame(inv_records)
    assert len(df) == 45, f"Expected 45 inventory rows, got {len(df)}"
    # Strict identity check
    assert (df["total_usable_stock"] == df["usable_stock_mt_qc"] + df["usable_stock_gt_only"]).all()
    # Check near-cliff flags
    mpb_east = df[(df["sku_id"] == "PR-MPB") & (df["depot_id"] == "Depot-East-01")].iloc[0]
    assert mpb_east["remaining_shelf_life_days"] == 63
    assert mpb_east["near_cliff_stock"] > 0

    return df


# ==============================================================================
# 6. INBOUND SHIPMENTS (20 ROWS, MARCH-JUNE SPAN, UNIQUE IDS)
# ==============================================================================
def generate_inbound_shipments() -> pd.DataFrame:
    """Generate 20 inbound shipments across March, April, May, and June."""
    shipments = [
        # March Shipments (Delivered)
        {"shipment_id": "SHP-2026-0310-01", "sku_id": "PR-MPB", "destination_depot_id": "Depot-North-01", "qty_bottles": 50000, "origin_type": "PLANT", "origin_id": "Plant-West-01", "dispatch_date": "2026-03-08", "expected_arrival_date": "2026-03-10", "actual_arrival_date": "2026-03-10", "status": "DELIVERED", "is_on_time": True, "is_in_full": True},
        {"shipment_id": "SHP-2026-0315-02", "sku_id": "PR-DP", "destination_depot_id": "Depot-West-01", "qty_bottles": 40000, "origin_type": "PLANT", "origin_id": "Plant-West-01", "dispatch_date": "2026-03-13", "expected_arrival_date": "2026-03-15", "actual_arrival_date": "2026-03-15", "status": "DELIVERED", "is_on_time": True, "is_in_full": True},
        {"shipment_id": "SHP-2026-0320-03", "sku_id": "PR-GC", "destination_depot_id": "Depot-South-01", "qty_bottles": 35000, "origin_type": "PLANT", "origin_id": "Plant-South-01", "dispatch_date": "2026-03-18", "expected_arrival_date": "2026-03-20", "actual_arrival_date": "2026-03-20", "status": "DELIVERED", "is_on_time": True, "is_in_full": True},
        {"shipment_id": "SHP-2026-0328-04", "sku_id": "PR-PP", "destination_depot_id": "Depot-Central-01", "qty_bottles": 28000, "origin_type": "PLANT", "origin_id": "Plant-West-01", "dispatch_date": "2026-03-25", "expected_arrival_date": "2026-03-28", "actual_arrival_date": "2026-03-28", "status": "DELIVERED", "is_on_time": True, "is_in_full": True},

        # April Shipments (Delivered & Delayed)
        {"shipment_id": "SHP-2026-0405-05", "sku_id": "PR-MPB", "destination_depot_id": "Depot-East-01", "qty_bottles": 65000, "origin_type": "PLANT", "origin_id": "Plant-South-01", "dispatch_date": "2026-04-02", "expected_arrival_date": "2026-04-05", "actual_arrival_date": "2026-04-05", "status": "DELIVERED", "is_on_time": True, "is_in_full": True},
        {"shipment_id": "SHP-2026-0412-06", "sku_id": "PR-GC", "destination_depot_id": "Depot-North-01", "qty_bottles": 30000, "origin_type": "PLANT", "origin_id": "Plant-West-01", "dispatch_date": "2026-04-09", "expected_arrival_date": "2026-04-12", "actual_arrival_date": "2026-04-14", "status": "DELIVERED", "is_on_time": False, "is_in_full": True},
        {"shipment_id": "SHP-2026-0418-07", "sku_id": "PR-DB", "destination_depot_id": "Depot-West-02", "qty_bottles": 22000, "origin_type": "PLANT", "origin_id": "Plant-West-01", "dispatch_date": "2026-04-15", "expected_arrival_date": "2026-04-18", "actual_arrival_date": "2026-04-18", "status": "DELIVERED", "is_on_time": True, "is_in_full": True},
        {"shipment_id": "SHP-2026-0425-08", "sku_id": "PR-DP", "destination_depot_id": "Depot-South-02", "qty_bottles": 45000, "origin_type": "PLANT", "origin_id": "Plant-South-01", "dispatch_date": "2026-04-22", "expected_arrival_date": "2026-04-25", "actual_arrival_date": "2026-04-25", "status": "DELIVERED", "is_on_time": True, "is_in_full": True},

        # May Shipments (Highway Closure window & In-Transit)
        {"shipment_id": "SHP-2026-0504-09", "sku_id": "PR-PP", "destination_depot_id": "Depot-North-01", "qty_bottles": 35000, "origin_type": "PLANT", "origin_id": "Plant-West-01", "dispatch_date": "2026-05-01", "expected_arrival_date": "2026-05-04", "actual_arrival_date": "2026-05-04", "status": "DELIVERED", "is_on_time": True, "is_in_full": True},
        {"shipment_id": "SHP-2026-0511-10", "sku_id": "PR-MPB", "destination_depot_id": "Depot-Central-01", "qty_bottles": 40000, "origin_type": "PLANT", "origin_id": "Plant-West-01", "dispatch_date": "2026-05-08", "expected_arrival_date": "2026-05-11", "actual_arrival_date": "2026-05-11", "status": "DELIVERED", "is_on_time": True, "is_in_full": True},
        {"shipment_id": "SHP-2026-0518-11", "sku_id": "PR-DP", "destination_depot_id": "Depot-West-01", "qty_bottles": 32000, "origin_type": "PLANT", "origin_id": "Plant-West-01", "dispatch_date": "2026-05-19", "expected_arrival_date": "2026-05-22", "actual_arrival_date": "", "status": "IN_TRANSIT", "is_on_time": True, "is_in_full": True},
        {"shipment_id": "SHP-2026-0519-12", "sku_id": "PR-GC", "destination_depot_id": "Depot-North-01", "qty_bottles": 28000, "origin_type": "PLANT", "origin_id": "Plant-West-01", "dispatch_date": "2026-05-18", "expected_arrival_date": "2026-05-21", "actual_arrival_date": "", "status": "IN_TRANSIT", "is_on_time": True, "is_in_full": True},
        {"shipment_id": "SHP-2026-0520-13", "sku_id": "PR-DB", "destination_depot_id": "Depot-South-01", "qty_bottles": 25000, "origin_type": "PLANT", "origin_id": "Plant-South-01", "dispatch_date": "2026-05-18", "expected_arrival_date": "2026-05-21", "actual_arrival_date": "", "status": "DELAYED", "is_on_time": False, "is_in_full": True},
        {"shipment_id": "SHP-2026-0520-14", "sku_id": "PR-PP", "destination_depot_id": "Depot-East-02", "qty_bottles": 18000, "origin_type": "PLANT", "origin_id": "Plant-South-01", "dispatch_date": "2026-05-19", "expected_arrival_date": "2026-05-23", "actual_arrival_date": "", "status": "IN_TRANSIT", "is_on_time": True, "is_in_full": True},
        {"shipment_id": "SHP-2026-0522-15", "sku_id": "PR-MPB", "destination_depot_id": "Depot-North-02", "qty_bottles": 35000, "origin_type": "PLANT", "origin_id": "Plant-West-01", "dispatch_date": "2026-05-20", "expected_arrival_date": "2026-05-23", "actual_arrival_date": "", "status": "IN_TRANSIT", "is_on_time": True, "is_in_full": True},

        # June Shipments (Co-packer activation & pre-monsoon stabilization)
        {"shipment_id": "SHP-2026-0602-16", "sku_id": "PR-DP", "destination_depot_id": "Depot-North-01", "qty_bottles": 40000, "origin_type": "COPACKER", "origin_id": "Copacker-Central-01", "dispatch_date": "2026-05-30", "expected_arrival_date": "2026-06-02", "actual_arrival_date": "2026-06-02", "status": "DELIVERED", "is_on_time": True, "is_in_full": True},
        {"shipment_id": "SHP-2026-0608-17", "sku_id": "PR-GC", "destination_depot_id": "Depot-West-01", "qty_bottles": 30000, "origin_type": "COPACKER", "origin_id": "Copacker-Central-01", "dispatch_date": "2026-06-05", "expected_arrival_date": "2026-06-08", "actual_arrival_date": "2026-06-08", "status": "DELIVERED", "is_on_time": True, "is_in_full": True},
        {"shipment_id": "SHP-2026-0615-18", "sku_id": "PR-PP", "destination_depot_id": "Depot-South-01", "qty_bottles": 28000, "origin_type": "PLANT", "origin_id": "Plant-South-01", "dispatch_date": "2026-06-13", "expected_arrival_date": "2026-06-16", "actual_arrival_date": "", "status": "IN_TRANSIT", "is_on_time": True, "is_in_full": True},
        {"shipment_id": "SHP-2026-0620-19", "sku_id": "PR-DB", "destination_depot_id": "Depot-Central-01", "qty_bottles": 22000, "origin_type": "PLANT", "origin_id": "Plant-West-01", "dispatch_date": "2026-06-17", "expected_arrival_date": "2026-06-20", "actual_arrival_date": "", "status": "IN_TRANSIT", "is_on_time": True, "is_in_full": True},
        {"shipment_id": "SHP-2026-0625-20", "sku_id": "PR-MPB", "destination_depot_id": "Depot-West-01", "qty_bottles": 50000, "origin_type": "COPACKER", "origin_id": "Copacker-Central-01", "dispatch_date": "2026-06-22", "expected_arrival_date": "2026-06-25", "actual_arrival_date": "", "status": "DELAYED", "is_on_time": False, "is_in_full": True},
    ]
    df = pd.DataFrame(shipments)
    assert len(df) == 20, f"Expected 20 inbound shipments, got {len(df)}"
    assert df["shipment_id"].nunique() == 20, "Shipment IDs must be unique"
    return df


# ==============================================================================
# 7. SUPPLIER STATUS (5 ROWS, SCM CONSTRAINTS)
# ==============================================================================
def generate_supplier_status() -> pd.DataFrame:
    """Generate 5 supplier rows modeling upstream materials and co-packer terms."""
    suppliers = [
        {
            "supplier_id": "SUP-PF-01",
            "material_name": "Passionfruit Pulp",
            "origin_location": "Hill-Region Cooperative Route",
            "transit_mode": "ROAD",
            "standard_lead_time_days": 3,
            "active_disruption_flag": True,
            "disruption_type": "HIGHWAY_CLOSURE",
            "effective_delay_days": 21,
            "notes": (
                "NH closed for 21 days in May due to landslides. Sole access road. Starting plant cover 14 days vs 21d closure. "
                "180d cold-storage shelf life. 28d recommended pre-summer buffer. Emergency air freight reference at 5.0x cost (₹3.20 Cr)."
            ),
        },
        {
            "supplier_id": "SUP-DF-01",
            "material_name": "Imported Dragonfruit Pulp",
            "origin_location": "Vietnam Maritime Corridor",
            "transit_mode": "SEA",
            "standard_lead_time_days": 49,
            "active_disruption_flag": False,
            "disruption_type": "QUARTERLY_IMPORT_CYCLE",
            "effective_delay_days": 0,
            "notes": "40% imported dragonfruit pulp for PR-DB. 49-56 days lead time (6-8 weeks quarterly cycle). Rigid forward container booking required.",
        },
        {
            "supplier_id": "SUP-MP-01",
            "material_name": "Mango-Peach Blend",
            "origin_location": "Domestic Multi-Supplier",
            "transit_mode": "ROAD",
            "standard_lead_time_days": 4,
            "active_disruption_flag": False,
            "disruption_type": "NONE",
            "effective_delay_days": 0,
            "notes": "Healthy domestic supply across western agricultural belt. 38% summer volume share.",
        },
        {
            "supplier_id": "SUP-GV-01",
            "material_name": "Guava Pulp",
            "origin_location": "Domestic Multi-Supplier",
            "transit_mode": "ROAD",
            "standard_lead_time_days": 3,
            "active_disruption_flag": False,
            "disruption_type": "NONE",
            "effective_delay_days": 0,
            "notes": "Stable domestic supply across cooperative clusters. 20% summer volume share.",
        },
        {
            "supplier_id": "COPACK-01",
            "material_name": "Co-Packer Bottling Facility",
            "origin_location": "Regional Bottling Partner",
            "transit_mode": "ROAD",
            "standard_lead_time_days": 14,
            "active_disruption_flag": False,
            "disruption_type": "NONE",
            "effective_delay_days": 0,
            "notes": "Co-packer provides bottling line capacity up to +10% volume at +25% cost premium with 14d advance notice; cannot solve raw pulp shortage.",
        },
    ]
    df = pd.DataFrame(suppliers)
    assert len(df) == 5, f"Expected 5 suppliers, got {len(df)}"
    return df


# ==============================================================================
# 8. RECOMMENDATIONS & 9. APPROVALS (CLEAN HISTORICAL + 6 VALIDATED PENDING)
# ==============================================================================
def generate_recommendations_and_approvals(
    existing_recs_df: Optional[pd.DataFrame] = None,
    existing_apps_df: Optional[pd.DataFrame] = None,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Generate recommendations and approvals preserving clean historical records and adding 6 pending actions.
    
    Removes corrupt test rows (like PR-OR).
    """
    valid_sku_set = set(SKUS.keys())

    # 1. Clean existing approvals and recommendations
    clean_approved_recs = []
    clean_approvals = []

    if existing_recs_df is not None and not existing_recs_df.empty:
        # Keep only APPROVED records with valid SKUs
        valid_recs = existing_recs_df[
            (existing_recs_df["status"] == "APPROVED") &
            (existing_recs_df["sku_id"].isin(valid_sku_set))
        ]
        valid_rec_ids = set(valid_recs["recommendation_id"].unique())

        if existing_apps_df is not None and not existing_apps_df.empty:
            valid_apps = existing_apps_df[existing_apps_df["recommendation_id"].isin(valid_rec_ids)]
            app_rec_ids = set(valid_apps["recommendation_id"].unique())
            # Match both directions
            valid_recs = valid_recs[valid_recs["recommendation_id"].isin(app_rec_ids)]
            clean_approved_recs = valid_recs.to_dict(orient="records")
            clean_approvals = valid_apps.to_dict(orient="records")

    # 2. Six Mathematically Validated PENDING Recommendations
    new_pending_recs = [
        {
            "recommendation_id": "REC-2026-0520-101",
            "created_at": "2026-05-20 08:00:00",
            "priority": "P1",
            "module": "DISTRIBUTION",
            "sku_id": "PR-DP",
            "origin_depot_id": "Depot-South-02",
            "destination_depot_id": "Depot-West-01",
            "action_type": "INTER_DEPOT_TRANSFER",
            "quantity_bottles": 18000,
            "cost_inr": 27000.0,  # 18,000 * ₹1.50
            "protected_contribution_inr": 345600.0,  # 18,000 * ₹60 * 32%
            "lead_time_days": 3,
            "eta_days": 4,
            "shelf_life_status": "PASS (76d remaining >= 67d gate)",
            "donor_post_cover_days": 23.5,  # Preserves >= 21d target
            "destination_post_cover_days": 8.5,
            "shortage_reduction_bottles": 18000,
            "status": "PENDING",
            "confidence_level": "HIGH",
            "diagnosis": "PR-DP @ Depot-West-01 projected stock-out in 3.5 days from 4x QC velocity surge. Depot-South-02 has 32d cover and can safely donate 18,000 btls.",
            "is_synthetic": True,
        },
        {
            "recommendation_id": "REC-2026-0520-102",
            "created_at": "2026-05-20 08:15:00",
            "priority": "P1",
            "module": "DISTRIBUTION",
            "sku_id": "PR-GC",
            "origin_depot_id": "Depot-South-01",
            "destination_depot_id": "Depot-North-01",
            "action_type": "INTER_DEPOT_TRANSFER",
            "quantity_bottles": 22000,
            "cost_inr": 33000.0,  # 22,000 * ₹1.50
            "protected_contribution_inr": 422400.0,
            "lead_time_days": 2,
            "eta_days": 3,
            "shelf_life_status": "PASS (75d remaining >= 67d gate)",
            "donor_post_cover_days": 21.8,  # Preserves >= 21d target
            "destination_post_cover_days": 16.2,
            "shortage_reduction_bottles": 22000,
            "status": "PENDING",
            "confidence_level": "HIGH",
            "diagnosis": "PR-GC @ Depot-North-01 has 9.0d cover. Depot-South-01 holds 29.0d surplus.",
            "is_synthetic": True,
        },
        {
            "recommendation_id": "REC-2026-0520-103",
            "created_at": "2026-05-20 08:30:00",
            "priority": "P1",
            "module": "PULP_RATIONING",
            "sku_id": "PR-PP",
            "origin_depot_id": "Plant-Central",
            "destination_depot_id": "NETWORK",
            "action_type": "RATION_RECIPE",
            "quantity_bottles": 35000,
            "cost_inr": 0.0,
            "protected_contribution_inr": 672000.0,
            "lead_time_days": 1,
            "eta_days": 2,
            "shelf_life_status": "PASS",
            "donor_post_cover_days": 14.0,
            "destination_post_cover_days": 18.0,
            "shortage_reduction_bottles": 35000,
            "status": "PENDING",
            "confidence_level": "HIGH",
            "diagnosis": "Passionfruit highway disruption: Ration PR-PP by -30% to protect high-margin PR-DP contractual Modern Trade commitments. Co-packer cannot solve raw pulp shortage.",
            "is_synthetic": True,
        },
        {
            "recommendation_id": "REC-2026-0520-104",
            "created_at": "2026-05-20 08:45:00",
            "priority": "P2",
            "module": "SHELF_LIFE",
            "sku_id": "PR-MPB",
            "origin_depot_id": "Depot-East-01",
            "destination_depot_id": "LOCAL_GT",
            "action_type": "FEFO_GT_REALLOCATION",
            "quantity_bottles": 25000,
            "cost_inr": 0.0,
            "protected_contribution_inr": 480000.0,
            "lead_time_days": 1,
            "eta_days": 1,
            "shelf_life_status": "FAIL_MT_QC_TRANSFER (63d batch age <= 67d gate)",
            "donor_post_cover_days": 21.5,
            "destination_post_cover_days": 21.0,
            "shortage_reduction_bottles": 25000,
            "status": "PENDING",
            "confidence_level": "HIGH",
            "diagnosis": "Depot-East-01 holds 63d batch age PR-MPB (near-cliff). MT/QC inter-depot transfer blocked; execute immediate local General Trade reallocation via FEFO.",
            "is_synthetic": True,
        },
        {
            "recommendation_id": "REC-2026-0520-105",
            "created_at": "2026-05-20 09:00:00",
            "priority": "P2",
            "module": "DISTRIBUTION",
            "sku_id": "PR-DP",
            "origin_depot_id": "Depot-South-01",
            "destination_depot_id": "Depot-North-01",
            "action_type": "INTER_DEPOT_TRANSFER",
            "quantity_bottles": 12000,
            "cost_inr": 18000.0,  # 12,000 * ₹1.50
            "protected_contribution_inr": 230400.0,
            "lead_time_days": 3,
            "eta_days": 4,
            "shelf_life_status": "PASS (74d remaining >= 67d gate)",
            "donor_post_cover_days": 22.4,  # Preserves >= 21d target
            "destination_post_cover_days": 12.0,
            "shortage_reduction_bottles": 12000,
            "status": "PENDING",
            "confidence_level": "MEDIUM",
            "diagnosis": "PR-DP viral velocity in Delhi outstrips inbound dispatches. Rebalance 12,000 btls from Bengaluru buffer.",
            "is_synthetic": True,
        },
        {
            "recommendation_id": "REC-2026-0520-106",
            "created_at": "2026-05-20 09:15:00",
            "priority": "P2",
            "module": "DISTRIBUTION",
            "sku_id": "PR-GC",
            "origin_depot_id": "Depot-West-02",
            "destination_depot_id": "Depot-North-02",
            "action_type": "INTER_DEPOT_TRANSFER",
            "quantity_bottles": 15000,
            "cost_inr": 22500.0,  # 15,000 * ₹1.50
            "protected_contribution_inr": 288000.0,
            "lead_time_days": 2,
            "eta_days": 3,
            "shelf_life_status": "PASS (77d remaining >= 67d gate)",
            "donor_post_cover_days": 23.0,  # Preserves >= 21d target
            "destination_post_cover_days": 18.5,
            "shortage_reduction_bottles": 15000,
            "status": "PENDING",
            "confidence_level": "MEDIUM",
            "diagnosis": "Rebalance 15,000 btls PR-GC from Ahmedabad surplus to Lucknow regional depot to support northern summer surge.",
            "is_synthetic": True,
        },
    ]

    all_recs = clean_approved_recs + new_pending_recs
    recs_df = pd.DataFrame(all_recs).drop_duplicates(subset=["recommendation_id"])

    # If no historical approvals exist, generate initial seed approvals
    if not clean_approvals:
        clean_approvals = [
            {
                "approval_id": "APP-2026-0518-01",
                "recommendation_id": "REC-2026-0520-101",  # Initial historical approval example
                "decision": "APPROVED",
                "decided_at": "2026-05-18 11:00:00",
                "approver_id": "COO-EXECUTIVE",
                "approver_role": "Chief Operating Officer",
                "modified_quantity_bottles": None,
                "notes": "Verified donor retains >=21d cover and batch shelf life passes MT/QC gate.",
            }
        ]

    apps_df = pd.DataFrame(clean_approvals).drop_duplicates(subset=["approval_id"])
    return recs_df, apps_df


# ==============================================================================
# 9. ALARMS (7 ROWS, DEDUPLICATED, PRESERVES USER ACKNOWLEDGEMENTS)
# ==============================================================================
def generate_alarms(existing_alarms_df: Optional[pd.DataFrame] = None) -> pd.DataFrame:
    """Generate exactly 7 deduplicated alarms across the 5 alert categories.
    
    Preserves user acknowledgements and read states from existing alarms.
    """
    preserved_states = {}
    if existing_alarms_df is not None and not existing_alarms_df.empty:
        for _, row in existing_alarms_df.iterrows():
            a_id = str(row["alarm_id"])
            preserved_states[a_id] = {
                "status": row.get("status", "NEW"),
                "acknowledged_by": row.get("acknowledged_by"),
                "acknowledged_at": row.get("acknowledged_at"),
                "resolved_at": row.get("resolved_at"),
                "resolution_notes": row.get("resolution_notes"),
                "is_read": row.get("is_read", False),
            }

    alarms_data = [
        {
            "alarm_id": "ALARM-2026-0520-001",
            "created_at": "2026-05-20 08:00:00",
            "updated_at": "2026-05-20 08:00:00",
            "alarm_type": "DEMAND_SPIKE",
            "severity": "CRITICAL",
            "status": "NEW",
            "sku_id": "PR-DP",
            "depot_id": "Depot-West-01",
            "channel": "QC",
            "title": "Fourfold QC Demand Surge Detected",
            "description": "PR-DP daily sell-through in Mumbai accelerated 4.1x above baseline over 14 days following viral video.",
            "observed_value": "4.1x velocity",
            "threshold_value": "1.5x baseline",
            "source": "qc_daily_sell_through",
            "confidence_level": "HIGH",
            "recommended_action": "Execute inter-depot rebalancing from Depot-South-02 (REC-2026-0520-101).",
            "recommendation_id": "REC-2026-0520-101",
            "acknowledged_by": None,
            "acknowledged_at": None,
            "resolved_at": None,
            "resolution_notes": None,
            "is_synthetic": True,
            "is_read": True,
        },
        {
            "alarm_id": "ALARM-2026-0520-002",
            "created_at": "2026-05-20 08:05:00",
            "updated_at": "2026-05-20 08:05:00",
            "alarm_type": "SUPPLY_DISRUPTION",
            "severity": "CRITICAL",
            "status": "NEW",
            "sku_id": "PR-PP",
            "depot_id": "Depot-North-01",
            "channel": "ALL",
            "title": "Passionfruit Highway Closure (21 Days)",
            "description": "Hill-region cooperative road access disrupted by landslides for 21 days. Plant cover at 14 days.",
            "observed_value": "14 days cover",
            "threshold_value": "21 days target",
            "source": "supplier_status",
            "confidence_level": "HIGH",
            "recommended_action": "Ration PR-PP by -30% to protect PR-DP (REC-2026-0520-103).",
            "recommendation_id": "REC-2026-0520-103",
            "acknowledged_by": None,
            "acknowledged_at": None,
            "resolved_at": None,
            "resolution_notes": None,
            "is_synthetic": True,
            "is_read": True,
        },
        {
            "alarm_id": "ALARM-2026-0520-003",
            "created_at": "2026-05-20 08:10:00",
            "updated_at": "2026-05-20 08:10:00",
            "alarm_type": "SHELF_LIFE_CLIFF",
            "severity": "WARNING",
            "status": "NEW",
            "sku_id": "PR-MPB",
            "depot_id": "Depot-East-01",
            "channel": "MT",
            "title": "Near-Cliff Stock (60-67d Remaining)",
            "description": "Depot-East-01 holds 35% PR-MPB stock in 60-67d window. Transfer to MT/QC is blocked.",
            "observed_value": "63 days remaining",
            "threshold_value": "67 days near-cliff",
            "source": "inventory",
            "confidence_level": "HIGH",
            "recommended_action": "Route immediately to General Trade via FEFO (REC-2026-0520-104).",
            "recommendation_id": "REC-2026-0520-104",
            "acknowledged_by": None,
            "acknowledged_at": None,
            "resolved_at": None,
            "resolution_notes": None,
            "is_synthetic": True,
            "is_read": True,
        },
        {
            "alarm_id": "ALARM-2026-0520-004",
            "created_at": "2026-05-20 08:15:00",
            "updated_at": "2026-05-20 08:15:00",
            "alarm_type": "PROJECTED_STOCKOUT",
            "severity": "CRITICAL",
            "status": "NEW",
            "sku_id": "PR-DP",
            "depot_id": "Depot-West-01",
            "channel": "ALL",
            "title": "Projected Stock-Out in 3.5 Days",
            "description": "Unmitigated daily depletion will exhaust Depot-West-01 inventory within 3.5 days.",
            "observed_value": "3.5 days cover",
            "threshold_value": "7.0 days critical",
            "source": "inventory",
            "confidence_level": "HIGH",
            "recommended_action": "Approve 18,000 btls transfer from Depot-South-02 (REC-2026-0520-101).",
            "recommendation_id": "REC-2026-0520-101",
            "acknowledged_by": None,
            "acknowledged_at": None,
            "resolved_at": None,
            "resolution_notes": None,
            "is_synthetic": True,
            "is_read": False,
        },
        {
            "alarm_id": "ALARM-2026-0520-005",
            "created_at": "2026-05-20 08:20:00",
            "updated_at": "2026-05-20 08:20:00",
            "alarm_type": "PROJECTED_STOCKOUT",
            "severity": "CRITICAL",
            "status": "NEW",
            "sku_id": "PR-GC",
            "depot_id": "Depot-North-01",
            "channel": "ALL",
            "title": "Northern Regional Depletion Under 9 Days",
            "description": "Depot-North-01 cover dropped to 9.0 days due to regional demand shift.",
            "observed_value": "9.0 days cover",
            "threshold_value": "14.0 days warning",
            "source": "inventory",
            "confidence_level": "HIGH",
            "recommended_action": "Transfer 22,000 btls from Depot-South-01 surplus (REC-2026-0520-102).",
            "recommendation_id": "REC-2026-0520-102",
            "acknowledged_by": None,
            "acknowledged_at": None,
            "resolved_at": None,
            "resolution_notes": None,
            "is_synthetic": True,
            "is_read": False,
        },
        {
            "alarm_id": "ALARM-2026-0520-006",
            "created_at": "2026-05-20 08:25:00",
            "updated_at": "2026-05-20 08:25:00",
            "alarm_type": "SHELF_LIFE_CLIFF",
            "severity": "WARNING",
            "status": "NEW",
            "sku_id": "PR-MPB",
            "depot_id": "Depot-Central-01",
            "channel": "MT",
            "title": "Central Depot Aging Inventory (63 Days)",
            "description": "Depot-Central-01 holds 35% aging PR-MPB stock approaching 60-day MT/QC gate.",
            "observed_value": "63 days remaining",
            "threshold_value": "67 days near-cliff",
            "source": "inventory",
            "confidence_level": "HIGH",
            "recommended_action": "Route to General Trade via FEFO.",
            "recommendation_id": "REC-2026-0520-104",
            "acknowledged_by": None,
            "acknowledged_at": None,
            "resolved_at": None,
            "resolution_notes": None,
            "is_synthetic": True,
            "is_read": False,
        },
        {
            "alarm_id": "ALARM-2026-0520-007",
            "created_at": "2026-05-20 08:30:00",
            "updated_at": "2026-05-20 08:30:00",
            "alarm_type": "SHIPMENT_DELAY",
            "severity": "WARNING",
            "status": "NEW",
            "sku_id": "PR-DB",
            "depot_id": "Depot-South-01",
            "channel": "ALL",
            "title": "Imported Dragonfruit Pulp Inbound Lag",
            "description": "Quarterly sea shipment experiencing maritime corridor delay (effective delay 3 days).",
            "observed_value": "52 days transit",
            "threshold_value": "49 days lead time",
            "source": "inbound_shipments",
            "confidence_level": "MEDIUM",
            "recommended_action": "Monitor dragonfruit batch buffer and queue Copacker option if delayed further.",
            "recommendation_id": "REC-2026-0520-105",
            "acknowledged_by": None,
            "acknowledged_at": None,
            "resolved_at": None,
            "resolution_notes": None,
            "is_synthetic": True,
            "is_read": False,
        },
    ]

    # Re-apply preserved user acknowledgements
    for a in alarms_data:
        a_id = a["alarm_id"]
        if a_id in preserved_states:
            saved = preserved_states[a_id]
            a["status"] = saved["status"]
            a["acknowledged_by"] = saved["acknowledged_by"]
            a["acknowledged_at"] = saved["acknowledged_at"]
            a["resolved_at"] = saved["resolved_at"]
            a["resolution_notes"] = saved["resolution_notes"]
            a["is_read"] = saved["is_read"]

    df = pd.DataFrame(alarms_data)
    assert len(df) == 7, f"Expected 7 alarms, got {len(df)}"
    return df


# ==============================================================================
# 10. STOCKOUT REPORTS, 11. AUDIT LOG, 12. UPLOAD HISTORY, 13. WORKFLOW STATE
# ==============================================================================
def generate_stockout_reports(existing_df: Optional[pd.DataFrame] = None) -> pd.DataFrame:
    """Generate multi-month stockout reports while preserving manual reports."""
    seed_reports = [
        # March Viral Spike
        {
            "report_id": "REP-2026-0324-01",
            "reported_at": "2026-03-24 10:15:00",
            "depot_id": "Depot-West-01",
            "sku_id": "PR-DP",
            "channel": "QC",
            "reported_by": "Depot Ops Lead - Mumbai",
            "evidence_source": "Blinkit partner dark store inventory logs",
            "estimated_unmet_bottles": 24000,
            "notes": "Viral video spike accelerated QC demand 4x; stock depleted across 14 dark stores.",
        },
        {
            "report_id": "REP-2026-0326-02",
            "reported_at": "2026-03-26 14:30:00",
            "depot_id": "Depot-North-01",
            "sku_id": "PR-DP",
            "channel": "QC",
            "reported_by": "Area Sales Lead - Delhi",
            "evidence_source": "Zepto platform unfulfilled customer search logs",
            "estimated_unmet_bottles": 18500,
            "notes": "QC app registered zero stock across NCR dark stores.",
        },
        # April Allocation Gap
        {
            "report_id": "REP-2026-0416-03",
            "reported_at": "2026-04-16 11:20:00",
            "depot_id": "Depot-North-01",
            "sku_id": "PR-GC",
            "channel": "GT",
            "reported_by": "Regional Sales Manager - North",
            "evidence_source": "Distributor unfilled purchase orders",
            "estimated_unmet_bottles": 16200,
            "notes": "Summer heat surge created 9d cover deficit against historical allocation quotas.",
        },
        # May Highway Disruption
        {
            "report_id": "REP-2026-0518-04",
            "reported_at": "2026-05-18 10:30:00",
            "depot_id": "Depot-West-01",
            "sku_id": "PR-DP",
            "channel": "QC",
            "reported_by": "Depot Ops Lead - West",
            "evidence_source": "Blinkit/Zepto partner dark store stockout logs",
            "estimated_unmet_bottles": 28500,
            "notes": "QC orders zeroed out across 18 dark stores. Demand sensing triggered rebalancing.",
        },
        {
            "report_id": "REP-2026-0519-05",
            "reported_at": "2026-05-19 14:15:00",
            "depot_id": "Depot-North-01",
            "sku_id": "PR-PP",
            "channel": "GT",
            "reported_by": "GT Area Sales Manager - Delhi",
            "evidence_source": "Distributor unfilled PO slips",
            "estimated_unmet_bottles": 18200,
            "notes": "Passionfruit punch stock depleted due to highway transit cut.",
        },
    ]

    all_reports = seed_reports
    if existing_df is not None and not existing_df.empty:
        # Preserve user-entered field telemetry
        manual_rows = existing_df[~existing_df["report_id"].str.startswith("REP-2026-")].to_dict(orient="records")
        all_reports = seed_reports + manual_rows

    df = pd.DataFrame(all_reports).drop_duplicates(subset=["report_id"])
    return df


def generate_upload_history(existing_df: Optional[pd.DataFrame] = None) -> pd.DataFrame:
    """Generate multi-month data ingestion history across all summer months."""
    seed_uploads = [
        {"upload_id": "UPL-2026-0305-01", "uploaded_at": "2026-03-05 09:00:00", "uploader": "Demand Ops Telemetry", "source_channel": "Quick Commerce", "reporting_period": "2026-03-01 to 2026-03-05", "records_processed": 225, "records_inserted": 225, "duplicates_skipped": 0, "errors_count": 0},
        {"upload_id": "UPL-2026-0315-02", "uploaded_at": "2026-03-15 09:00:00", "uploader": "Distributor Feed", "source_channel": "Modern Trade", "reporting_period": "2026-03-06 to 2026-03-15", "records_processed": 450, "records_inserted": 450, "duplicates_skipped": 0, "errors_count": 0},
        {"upload_id": "UPL-2026-0331-03", "uploaded_at": "2026-03-31 18:00:00", "uploader": "S&OP Spreadsheet Consolidation", "source_channel": "General Trade", "reporting_period": "2026-03-01 to 2026-03-31", "records_processed": 1395, "records_inserted": 1395, "duplicates_skipped": 0, "errors_count": 0},
        {"upload_id": "UPL-2026-0415-04", "uploaded_at": "2026-04-15 09:00:00", "uploader": "Demand Ops Telemetry", "source_channel": "Quick Commerce", "reporting_period": "2026-04-01 to 2026-04-15", "records_processed": 675, "records_inserted": 675, "duplicates_skipped": 0, "errors_count": 0},
        {"upload_id": "UPL-2026-0430-05", "uploaded_at": "2026-04-30 18:00:00", "uploader": "S&OP Monthly Planner", "source_channel": "General Trade", "reporting_period": "2026-04-01 to 2026-04-30", "records_processed": 1350, "records_inserted": 1350, "duplicates_skipped": 0, "errors_count": 0},
        {"upload_id": "UPL-2026-0515-06", "uploaded_at": "2026-05-15 09:00:00", "uploader": "Demand Ops Telemetry", "source_channel": "Quick Commerce", "reporting_period": "2026-05-01 to 2026-05-15", "records_processed": 675, "records_inserted": 675, "duplicates_skipped": 0, "errors_count": 0},
        {"upload_id": "UPL-2026-0520-07", "uploaded_at": "2026-05-20 08:00:00", "uploader": "S&OP Demand Sensing Pipeline", "source_channel": "All Channels", "reporting_period": "2026-05-13 to 2026-05-20", "records_processed": 315, "records_inserted": 315, "duplicates_skipped": 0, "errors_count": 0},
        {"upload_id": "UPL-2026-0610-08", "uploaded_at": "2026-06-10 09:00:00", "uploader": "Co-Packer Telemetry Connector", "source_channel": "Modern Trade", "reporting_period": "2026-06-01 to 2026-06-10", "records_processed": 450, "records_inserted": 450, "duplicates_skipped": 0, "errors_count": 0},
        {"upload_id": "UPL-2026-0630-09", "uploaded_at": "2026-06-30 18:00:00", "uploader": "Quarterly S&OP Audit Feed", "source_channel": "All Channels", "reporting_period": "2026-03-01 to 2026-06-30", "records_processed": 5490, "records_inserted": 5490, "duplicates_skipped": 0, "errors_count": 0},
    ]

    all_uploads = seed_uploads
    if existing_df is not None and not existing_df.empty:
        # Preserve user uploads
        user_rows = existing_df[~existing_df["upload_id"].str.startswith("UPL-2026-")].to_dict(orient="records")
        all_uploads = seed_uploads + user_rows

    df = pd.DataFrame(all_uploads).drop_duplicates(subset=["upload_id"])
    return df


def generate_audit_log(existing_df: Optional[pd.DataFrame] = None) -> pd.DataFrame:
    """Generate clean audit log records preserving human events and removing corrupt rows."""
    seed_audit = [
        {
            "event_id": "AUD-2026-0520-001",
            "timestamp": "2026-05-20 08:30:00",
            "event_type": "PIPELINE_RUN",
            "entity_type": "SYSTEM",
            "entity_id": "SYS-SOP-V2",
            "actor_id": "Sensing-Engine",
            "action": "DEMAND_SENSING_EXECUTION",
            "details_json": '{"status": "SUCCESS", "vintages_evaluated": 17, "anomalies_detected": 4}',
        },
        {
            "event_id": "AUD-2026-0520-002",
            "timestamp": "2026-05-20 08:35:00",
            "event_type": "ALARM_GENERATION",
            "entity_type": "ALARM",
            "entity_id": "ALARM-2026-0520-001",
            "actor_id": "RiskService",
            "action": "TRIGGER_DEMAND_SPIKE",
            "details_json": '{"sku_id": "PR-DP", "depot_id": "Depot-West-01", "severity": "CRITICAL"}',
        },
        {
            "event_id": "AUD-2026-0520-003",
            "timestamp": "2026-05-20 08:40:00",
            "event_type": "RECOMMENDATION_DISPATCH",
            "entity_type": "RECOMMENDATION",
            "entity_id": "REC-2026-0520-101",
            "actor_id": "DistributionService",
            "action": "PROPOSE_TRANSFER",
            "details_json": '{"quantity": 18000, "cost_inr": 27000.0, "donor": "Depot-South-02"}',
        },
    ]

    all_audit = seed_audit
    if existing_df is not None and not existing_df.empty:
        # Keep non-corrupt existing audit records (exclude invalid PR-OR references)
        clean_existing = existing_df[~existing_df["details_json"].astype(str).str.contains("PR-OR")].to_dict(orient="records")
        all_audit = seed_audit + clean_existing

    df = pd.DataFrame(all_audit).drop_duplicates(subset=["event_id"])
    return df


def generate_workflow_state(existing_df: Optional[pd.DataFrame] = None) -> pd.DataFrame:
    """Generate workflow state entries for all active pipelines."""
    seed_states = [
        {"run_id": "RUN-2026-0520-001", "timestamp": "2026-05-20 08:00:00", "pipeline_name": "weekly_intelligence_pipeline", "step_name": "DATA_INGESTION", "status": "SUCCESS", "payload_json": '{"records": 5490}'},
        {"run_id": "RUN-2026-0520-001", "timestamp": "2026-05-20 08:05:00", "pipeline_name": "weekly_intelligence_pipeline", "step_name": "DEMAND_SENSING", "status": "SUCCESS", "payload_json": '{"wape_corr": 10.7}'},
        {"run_id": "RUN-2026-0520-001", "timestamp": "2026-05-20 08:10:00", "pipeline_name": "weekly_intelligence_pipeline", "step_name": "REBALANCING_OPTIMIZATION", "status": "SUCCESS", "payload_json": '{"proposals": 6}'},
        {"run_id": "RUN-2026-0520-001", "timestamp": "2026-05-20 08:15:00", "pipeline_name": "weekly_intelligence_pipeline", "step_name": "REPORT_PUBLICATION", "status": "SUCCESS", "payload_json": '{"pages": 3, "pdf": "weekly_intelligence_report_2026-W18.pdf"}'},
    ]

    all_states = seed_states
    if existing_df is not None and not existing_df.empty:
        user_states = existing_df.to_dict(orient="records")
        all_states = seed_states + user_states

    df = pd.DataFrame(all_states).drop_duplicates(subset=["run_id", "step_name"])
    return df


# ==============================================================================
# MAIN GENERATION PIPELINE
# ==============================================================================
def run_generator(
    data_dir_str: str = "data",
    seed: int = 42,
    start_date: str = "2026-03-01",
    end_date: str = "2026-06-30",
    backup_dir_str: str = ".backups/csv_seed_backup",
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Execute complete 4-month summer synthetic dataset generation."""
    data_dir = Path(data_dir_str)
    backup_dir = Path(backup_dir_str)

    print("================================================================================")
    print("      RIOT RADAR — 4-MONTH SUMMER SYNTHETIC DATASET GENERATOR (122 DAYS)        ")
    print("================================================================================")
    print(f"Target Directory: {data_dir.resolve()}")
    print(f"Date Range:       {start_date} to {end_date} (122 days)")
    print(f"Random Seed:      {seed}")
    print(f"Dry Run Mode:     {dry_run}")
    print("--------------------------------------------------------------------------------")

    # Read existing CSVs for state preservation if available
    existing_recs = None
    existing_apps = None
    existing_alarms = None
    existing_reports = None
    existing_uploads = None
    existing_audit = None
    existing_workflow = None

    if data_dir.exists():
        if (data_dir / "recommendations.csv").exists():
            existing_recs = pd.read_csv(data_dir / "recommendations.csv")
        if (data_dir / "approvals.csv").exists():
            existing_apps = pd.read_csv(data_dir / "approvals.csv")
        if (data_dir / "alarms.csv").exists():
            existing_alarms = pd.read_csv(data_dir / "alarms.csv")
        if (data_dir / "stockout_reports.csv").exists():
            existing_reports = pd.read_csv(data_dir / "stockout_reports.csv")
        if (data_dir / "upload_history.csv").exists():
            existing_uploads = pd.read_csv(data_dir / "upload_history.csv")
        if (data_dir / "audit_log.csv").exists():
            existing_audit = pd.read_csv(data_dir / "audit_log.csv")
        if (data_dir / "workflow_state.csv").exists():
            existing_workflow = pd.read_csv(data_dir / "workflow_state.csv")

    # 1. Depots & 2. Products
    depots_df = generate_depots()
    products_df = generate_products()

    # 3. Demand History (5,490 rows)
    demand_df = generate_demand_history(start_date, end_date, seed)

    # 4. Forecast Snapshots (765 rows)
    forecast_df = generate_forecast_snapshots(demand_df, seed)

    # 5. Inventory (45 rows)
    inventory_df = generate_inventory(demand_df)

    # 6. Inbound Shipments (20 rows)
    shipments_df = generate_inbound_shipments()

    # 7. Supplier Status (5 rows)
    suppliers_df = generate_supplier_status()

    # 8. Recommendations & 9. Approvals
    recs_df, apps_df = generate_recommendations_and_approvals(existing_recs, existing_apps)

    # 10. Alarms (7 rows)
    alarms_df = generate_alarms(existing_alarms)

    # 11. Stockout Reports, 12. Upload History, 13. Audit Log, 14. Workflow State
    reports_df = generate_stockout_reports(existing_reports)
    uploads_df = generate_upload_history(existing_uploads)
    audit_df = generate_audit_log(existing_audit)
    workflow_df = generate_workflow_state(existing_workflow)

    all_tables = {
        "depots": depots_df,
        "products": products_df,
        "demand_history": demand_df,
        "forecast_snapshots": forecast_df,
        "inventory": inventory_df,
        "inbound_shipments": shipments_df,
        "supplier_status": suppliers_df,
        "recommendations": recs_df,
        "approvals": apps_df,
        "alarms": alarms_df,
        "stockout_reports": reports_df,
        "upload_history": uploads_df,
        "audit_log": audit_df,
        "workflow_state": workflow_df,
    }

    # Summary Statistics
    tot_corr = int(demand_df["corrected_demand"].sum())
    tot_cens = int(demand_df["censored_adjustment"].sum())
    tot_obs = int(demand_df["observed_sales"].sum())
    cens_pct = round(tot_cens / tot_corr * 100.0, 2)
    lost_rev_cr = round(tot_cens * BOTTLE_PRICE_INR / 1e7, 2)
    foregone_margin_cr = round(lost_rev_cr * (CONTRIBUTION_MARGIN_PCT / 100.0), 2)

    print("\nDATASET STATISTICAL RECONCILIATION:")
    print(f"  Total Corrected Demand:   {tot_corr:,} bottles (₹{tot_corr * BOTTLE_PRICE_INR / 1e7:.2f} Cr)")
    print(f"  Total Censored Volume:    {tot_cens:,} bottles ({cens_pct:.2f}% | Lost Revenue: ₹{lost_rev_cr:.2f} Cr | Margin: ₹{foregone_margin_cr:.2f} Cr)")
    print(f"  Total Observed Sales:     {tot_obs:,} bottles (₹{tot_obs * BOTTLE_PRICE_INR / 1e7:.2f} Cr)")
    print("\nROW COUNTS ACROSS ALL 14 CSV TABLES:")
    for name, df in all_tables.items():
        print(f"  - {name + '.csv':<24}: {len(df):>5} rows")

    if not dry_run:
        # Backup before overwriting
        if data_dir.exists():
            backed_up = backup_existing_csvs(data_dir, backup_dir)
            print(f"\nCreated backup of {backed_up} CSV files in: {backup_dir}")

        # Atomic writes for all 14 CSVs
        data_dir.mkdir(parents=True, exist_ok=True)
        for name, df in all_tables.items():
            atomic_save_csv(data_dir / f"{name}.csv", df)
        print(f"\nAll 14 CSV files successfully saved atomically to: {data_dir.resolve()}")
    else:
        print("\nDRY-RUN COMPLETE: No files were modified on disk.")

    return {
        "status": "SUCCESS",
        "total_corrected_demand": tot_corr,
        "total_censored_volume": tot_cens,
        "total_observed_sales": tot_obs,
        "censored_pct": cens_pct,
        "row_counts": {name: len(df) for name, df in all_tables.items()},
    }


if __name__ == "__main__":
    parser = get_cli_parser()
    args = parser.parse_args()
    run_generator(
        data_dir_str=args.data_dir,
        seed=args.seed,
        start_date=args.start_date,
        end_date=args.end_date,
        backup_dir_str=args.backup_dir,
        dry_run=args.dry_run,
    )
