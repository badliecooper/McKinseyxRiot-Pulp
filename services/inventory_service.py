"""Inventory Service for RIOT RADAR.

Calculates:
- Usable inventory segmented by channel eligibility (MT/QC eligible >= 60d vs GT-only < 60d)
- 67-day Near-Cliff Warning exposure
- Days of Cover (DoC) relative to 21-day target with safe zero-demand handling
- Projected stock-out dates with dated inbound receipts trajectory
"""

import datetime
from typing import Dict, List, Optional, Any
import pandas as pd
import numpy as np

from config.business_rules import (
    DEFAULT_TARGET_COVER_DAYS,
    NEAR_CLIFF_WARNING_DAYS,
    MT_QC_MIN_SHELF_LIFE_DAYS,
)
from services.csv_store import load_csv


def calculate_days_of_cover(usable_inventory: float, daily_demand: float) -> Optional[float]:
    """Calculate Days of Cover (DoC) = Usable Inventory / Daily Demand.
    
    Conventions for edge cases:
    - If daily_demand <= 0 and usable_inventory > 0: returns None (infinite / unconstrained cover).
    - If daily_demand <= 0 and usable_inventory <= 0: returns 0.0.
    - If usable_inventory <= 0: returns 0.0.
    """
    if usable_inventory is None or usable_inventory <= 0:
        return 0.0
    if daily_demand is None or daily_demand <= 0:
        return None  # Disclosed convention: None denotes zero-demand SKU with stock
    return float(usable_inventory / daily_demand)


def calculate_target_stock(daily_demand: float, target_cover_days: float = DEFAULT_TARGET_COVER_DAYS) -> float:
    """Calculate Target Stock = Corrected Forecast Daily Demand * Target Cover Days."""
    if daily_demand is None or daily_demand <= 0:
        return 0.0
    return float(round(daily_demand * target_cover_days))


def calculate_allocation_gap(target_stock: float, projected_usable_inventory: float) -> float:
    """Calculate Allocation Gap = Target Stock - Projected Usable Inventory.
    
    Positive gap indicates a shortage relative to the 21-day target.
    Negative gap indicates surplus stock.
    """
    target = target_stock if target_stock is not None else 0.0
    usable = projected_usable_inventory if projected_usable_inventory is not None else 0.0
    return float(round(target - usable))


class InventoryService:
    """Service handling inventory visibility, channel-segmented shelf life, and depletion trajectories."""

    def __init__(self):
        pass

    def get_inventory_table(
        self,
        sku_id: Optional[str] = None,
        depot_id: Optional[str] = None,
    ) -> pd.DataFrame:
        """Fetch inventory table with numeric conversions."""
        df = load_csv("inventory")
        if df.empty:
            return df

        df["usable_stock_mt_qc"] = pd.to_numeric(df["usable_stock_mt_qc"], errors="coerce").fillna(0)
        df["usable_stock_gt_only"] = pd.to_numeric(df["usable_stock_gt_only"], errors="coerce").fillna(0)
        df["near_cliff_stock"] = pd.to_numeric(df["near_cliff_stock"], errors="coerce").fillna(0)
        df["total_usable_stock"] = pd.to_numeric(df["total_usable_stock"], errors="coerce").fillna(0)
        df["remaining_shelf_life_days"] = pd.to_numeric(df["remaining_shelf_life_days"], errors="coerce").fillna(90)

        if sku_id:
            df = df[df["sku_id"] == sku_id]
        if depot_id:
            df = df[df["depot_id"] == depot_id]

        return df

    def get_sku_depot_inventory_status(
        self,
        sku_id: str,
        depot_id: str,
        daily_forecast_demand: float,
        target_cover_days: float = DEFAULT_TARGET_COVER_DAYS,
    ) -> Dict[str, Any]:
        """Get channel-segmented inventory, DoC, allocation gap, and cliff status for a SKU-Depot."""
        inv_df = self.get_inventory_table(sku_id, depot_id)
        
        if inv_df.empty:
            return {
                "sku_id": sku_id,
                "depot_id": depot_id,
                "usable_stock_mt_qc": 0,
                "usable_stock_gt_only": 0,
                "near_cliff_stock": 0,
                "total_usable_stock": 0,
                "target_stock": calculate_target_stock(daily_forecast_demand, target_cover_days),
                "allocation_gap": calculate_target_stock(daily_forecast_demand, target_cover_days),
                "days_of_cover": 0.0,
                "shelf_life_status": "NO_STOCK",
                "remaining_shelf_life_days": 0,
                "is_near_cliff": False,
            }

        row = inv_df.iloc[0]
        usable_mt_qc = float(row["usable_stock_mt_qc"])
        usable_gt_only = float(row["usable_stock_gt_only"])
        near_cliff = float(row["near_cliff_stock"])
        total_usable = float(row["total_usable_stock"])
        remaining_days = float(row["remaining_shelf_life_days"])

        doc = calculate_days_of_cover(total_usable, daily_forecast_demand)
        target_stock = calculate_target_stock(daily_forecast_demand, target_cover_days)
        gap = calculate_allocation_gap(target_stock, total_usable)

        # Shelf life status & 67-day cliff rule
        is_near_cliff = (remaining_days <= NEAR_CLIFF_WARNING_DAYS) and (remaining_days >= MT_QC_MIN_SHELF_LIFE_DAYS)
        is_mt_qc_expired = remaining_days < MT_QC_MIN_SHELF_LIFE_DAYS

        if is_mt_qc_expired:
            shelf_status = "GT_ONLY_RESTRICTED (Under 60d)"
        elif is_near_cliff:
            shelf_status = f"WARNING_NEAR_CLIFF ({int(remaining_days)}d remaining; Route to GT)"
        else:
            shelf_status = f"HEALTHY ({int(remaining_days)}d remaining)"

        return {
            "sku_id": sku_id,
            "depot_id": depot_id,
            "usable_stock_mt_qc": usable_mt_qc,
            "usable_stock_gt_only": usable_gt_only,
            "near_cliff_stock": near_cliff,
            "total_usable_stock": total_usable,
            "target_stock": target_stock,
            "allocation_gap": gap,
            "days_of_cover": round(doc, 1) if doc is not None else None,
            "shelf_life_status": shelf_status,
            "remaining_shelf_life_days": remaining_days,
            "is_near_cliff": is_near_cliff,
            "is_mt_qc_expired": is_mt_qc_expired,
            "is_synthetic": True,
        }

    def project_inventory_depletion_timeline(
        self,
        sku_id: str,
        depot_id: str,
        daily_forecast_demand: float,
        horizon_days: int = 21,
        start_date: Optional[datetime.date] = None,
    ) -> pd.DataFrame:
        """Project day-by-day inventory depletion and calculate projected stockout date.
        
        Accounts for scheduled dated inbound receipts (on-time arrivals).
        """
        if start_date is None:
            start_date = datetime.date(2026, 5, 20)

        inv_status = self.get_sku_depot_inventory_status(sku_id, depot_id, daily_forecast_demand)
        opening_stock = inv_status["total_usable_stock"]

        # Inbounds
        inbounds_df = load_csv("inbound_shipments")
        inbounds_for_sku_depot = pd.DataFrame()
        if not inbounds_df.empty:
            inbounds_df["qty_bottles"] = pd.to_numeric(inbounds_df["qty_bottles"], errors="coerce").fillna(0)
            inbounds_df["is_on_time"] = inbounds_df["is_on_time"].astype(str).str.lower().isin(["true", "1"])
            inbounds_for_sku_depot = inbounds_df[
                (inbounds_df["sku_id"] == sku_id)
                & (inbounds_df["destination_depot_id"] == depot_id)
                & (inbounds_df["status"] == "IN_TRANSIT")
            ]

        timeline_records = []
        curr_stock = opening_stock
        stockout_date_str = None

        # Approved transfers into this depot/SKU
        recs_df = load_csv("recommendations")
        transfers_for_cell = pd.DataFrame()
        if not recs_df.empty:
            recs_df["quantity_bottles"] = pd.to_numeric(recs_df["quantity_bottles"], errors="coerce").fillna(0)
            recs_df["eta_days"] = pd.to_numeric(recs_df["eta_days"], errors="coerce").fillna(3)
            transfers_for_cell = recs_df[
                (recs_df["sku_id"] == sku_id)
                & (recs_df["destination_depot_id"] == depot_id)
                & (recs_df["status"] == "APPROVED")
            ].copy()

        for d in range(horizon_days):
            curr_date = start_date + datetime.timedelta(days=d)
            date_str = curr_date.strftime("%Y-%m-%d")

            # 1. Opening stock for day d
            day_opening_stock = curr_stock

            # 2. Check inbound receipt today
            inbound_today = 0.0
            inbound_notes = []
            if not inbounds_for_sku_depot.empty:
                matches = inbounds_for_sku_depot[
                    inbounds_for_sku_depot["expected_arrival_date"] == date_str
                ]
                if not matches.empty:
                    inbound_today = float(matches["qty_bottles"].sum())
                    for _, m in matches.iterrows():
                        inbound_notes.append(f"Inbound {m.get('shipment_id', 'SHP')}: +{int(m['qty_bottles']):,} btls from {m.get('origin_id', 'Plant')}")

            # 3. Check approved inter-depot transfers arriving today
            transfer_today = 0.0
            transfer_notes = []
            if not transfers_for_cell.empty:
                for _, tr in transfers_for_cell.iterrows():
                    created_raw = str(tr.get("created_at", "2026-05-20"))[:10]
                    try:
                        c_date = datetime.datetime.strptime(created_raw, "%Y-%m-%d").date()
                    except Exception:
                        c_date = start_date
                    eta_d = int(tr.get("eta_days", 4))
                    arr_date = c_date + datetime.timedelta(days=eta_d)
                    if arr_date == curr_date:
                        t_qty = float(tr["quantity_bottles"])
                        transfer_today += t_qty
                        transfer_notes.append(f"Transfer {tr.get('recommendation_id', 'REC')}: +{int(t_qty):,} btls from {tr.get('origin_depot_id', 'Depot')}")

            # 4. Total available usable stock
            available_stock = day_opening_stock + inbound_today + transfer_today

            # 5. Fulfilled vs unmet demand (fulfilled <= available)
            demand_burn = float(daily_forecast_demand)
            fulfilled_demand = min(available_stock, demand_burn)
            unmet_demand = max(0.0, demand_burn - available_stock)

            # 6. Closing stock
            closing_stock = max(0.0, available_stock - fulfilled_demand)
            cover_days = round(closing_stock / demand_burn, 1) if demand_burn > 0 else 0.0

            # 7. Stock-out flag (closing stock 0 and unmet demand > 0)
            is_stocked_out = closing_stock <= 0 and unmet_demand > 0
            if (closing_stock <= 0 or is_stocked_out) and stockout_date_str is None:
                stockout_date_str = date_str

            # 8. Intervention note
            combined_notes = inbound_notes + transfer_notes
            note_str = "; ".join(combined_notes) if combined_notes else ""

            timeline_records.append({
                "date": date_str,
                "sku_id": sku_id,
                "depot_id": depot_id,
                "opening_stock": day_opening_stock,
                "inbound_receipt_qty": inbound_today,
                "transfer_in_qty": transfer_today,
                "available_usable_stock": available_stock,
                "daily_demand_burn": demand_burn,
                "fulfilled_demand": fulfilled_demand,
                "unmet_demand": unmet_demand,
                "closing_stock": closing_stock,
                "days_of_cover": cover_days,
                "is_stocked_out": is_stocked_out,
                "intervention_note": note_str,
                "data_type": "Observed" if d == 0 else "Calculated",
            })
            curr_stock = closing_stock

        timeline_df = pd.DataFrame(timeline_records)
        return timeline_df

    def get_projected_stockout_date(
        self,
        sku_id: str,
        depot_id: str,
        daily_forecast_demand: float,
        start_date: Optional[datetime.date] = None,
    ) -> Optional[str]:
        """Returns string YYYY-MM-DD of projected stockout or None if no stockout within 21d.
        
        Calculated as the first date where available usable stock is insufficient to fulfill demand.
        """
        timeline_df = self.project_inventory_depletion_timeline(
            sku_id, depot_id, daily_forecast_demand, horizon_days=21, start_date=start_date
        )
        stocked_out = timeline_df[timeline_df["is_stocked_out"]]
        if not stocked_out.empty:
            return str(stocked_out.iloc[0]["date"])
        return None
