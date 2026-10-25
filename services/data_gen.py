"""Data generator for RIOT RADAR.

Populates all 12 CSV tables with calibrated baseline records, historical demand series,
lot-age distributions, and disruption scenarios for the 45 SKU–Depot combinations.
Explicitly flags synthetic demo records as `is_synthetic=True`.
"""

import datetime
from typing import Dict, List, Any
import numpy as np
import pandas as pd

from config.business_rules import (
    SKUS,
    DEPOTS,
    CHANNEL_MIX,
    SUMMER_VOLUME_BOTTLES,
    DEFAULT_TARGET_COVER_DAYS,
    TRANSFER_COST_PER_BOTTLE_INR,
    NEAR_CLIFF_WARNING_DAYS,
    MT_QC_MIN_SHELF_LIFE_DAYS,
)
from services.csv_store import save_csv, load_csv, ensure_all_csvs


def generate_all_seed_data(seed: int = 42, force_regenerate: bool = False) -> None:
    """Generate and write all CSV files if they do not exist or if force_regenerate is True."""
    ensure_all_csvs()
    np.random.seed(seed)
    
    # 1. Depots
    depots_df = pd.DataFrame(DEPOTS)
    save_csv("depots", depots_df)
    
    # 2. Products
    products_data = []
    for sku_id, sku in SKUS.items():
        products_data.append({
            "sku_id": sku.sku_id,
            "flavour": sku.flavour,
            "summer_share_pct": sku.summer_share_pct,
            "primary_planning_concern": sku.primary_planning_concern,
            "pulp_type": sku.pulp_type,
            "pulp_kg_per_bottle": sku.pulp_kg_per_bottle,
        })
    products_df = pd.DataFrame(products_data)
    save_csv("products", products_df)
    
    # Check if demand_history already populated
    existing_demand = load_csv("demand_history")
    if not existing_demand.empty and not force_regenerate:
        return  # Already seeded
        
    # Total summer volume: 9.6 Cr bottles over 120 days = 800,000 bottles/day national demand
    total_daily_national_bottles = SUMMER_VOLUME_BOTTLES / 120.0  # 800,000 btls/day
    
    # Regional depot demand weights
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
    
    base_date = datetime.date(2026, 5, 20)
    history_days = 45  # 45 days of daily history
    
    demand_records = []
    inventory_records = []
    forecast_records = []
    inbound_records = []
    
    # Generate 45 SKU-Depot grain data
    for sku_id, sku in SKUS.items():
        sku_share = sku.summer_share_pct / 100.0
        
        for depot in DEPOTS:
            depot_id = depot["depot_id"]
            depot_weight = depot_weights.get(depot_id, 0.10)
            
            # Baseline unconstrained daily demand for this SKU-Depot
            base_daily_demand = total_daily_national_bottles * sku_share * depot_weight
            
            # Simulate historical days
            for day_offset in range(history_days):
                curr_date = base_date - datetime.timedelta(days=(history_days - 1 - day_offset))
                date_str = curr_date.strftime("%Y-%m-%d")
                
                # Check for special case scenario events
                is_viral_spike = False
                is_stockout_flagged = False
                viral_multiplier = 1.0
                
                # PR-DP viral spike in Depot-West-01 and Depot-North-01 in late May
                # Viral influencer video: 4x QC surge over 14 days
                if sku_id == "PR-DP" and depot_id in ["Depot-West-01", "Depot-North-01"]:
                    if day_offset >= 30:  # Last 15 days
                        ramp = min(4.0, 1.0 + (day_offset - 30) * 0.25)
                        viral_multiplier = ramp
                        is_viral_spike = True
                
                # Generate observed vs latent demand by channel
                # QC: 20%, MT: 25%, GT: 55%
                daily_total = base_daily_demand * viral_multiplier * np.random.normal(1.0, 0.08)
                daily_total = max(100.0, daily_total)
                
                # If PR-DP during viral spike in Depot-West-01, stock ran out at day_offset 37!
                stockout_factor = 1.0
                if sku_id == "PR-DP" and depot_id == "Depot-West-01" and day_offset >= 37:
                    is_stockout_flagged = True
                    stockout_factor = 0.15  # Only 15% observed sales because shelves were empty!
                
                # Also simulate slight stockout in PR-PP at Depot-North-01 due to highway closure
                if sku_id == "PR-PP" and depot_id == "Depot-North-01" and day_offset >= 38:
                    is_stockout_flagged = True
                    stockout_factor = 0.25
                
                corrected_demand = round(daily_total)
                observed_sales = round(daily_total * stockout_factor)
                censored_adjustment = corrected_demand - observed_sales
                
                # Channel assignment
                channel = "QC" if is_viral_spike else ("GT" if day_offset % 2 == 0 else "MT")
                
                demand_records.append({
                    "date": date_str,
                    "sku_id": sku_id,
                    "depot_id": depot_id,
                    "channel": channel,
                    "observed_sales": observed_sales,
                    "source_type": "qc_daily_sell_through" if is_viral_spike else "distributor_orders",
                    "freshness_lag_days": 1 if is_viral_spike else 7,
                    "is_stockout_flagged": is_stockout_flagged,
                    "censored_adjustment": censored_adjustment,
                    "corrected_demand": corrected_demand,
                    "is_synthetic": True,
                })
            
            # Current Opening Inventory calibrated to case situations
            # Target cover is 21 days
            target_stock = round(base_daily_demand * DEFAULT_TARGET_COVER_DAYS)
            
            # Special case calibration for specific SKU-Depots:
            if sku_id == "PR-DP" and depot_id == "Depot-West-01":
                # Stockout / severe shortage: 3.5 days of cover
                current_usable = round(base_daily_demand * 3.5)
                usable_mt_qc = round(current_usable * 0.90)
                usable_gt_only = current_usable - usable_mt_qc
                near_cliff = 0
                avg_remaining_days = 72
            elif sku_id == "PR-DP" and depot_id == "Depot-South-02":
                # Surplus donor for PR-DP: 32 days of cover
                current_usable = round(base_daily_demand * 32.0)
                usable_mt_qc = round(current_usable * 0.85)
                usable_gt_only = current_usable - usable_mt_qc
                near_cliff = round(current_usable * 0.05)
                avg_remaining_days = 76
            elif sku_id == "PR-MPB" and depot_id in ["Depot-East-01", "Depot-Central-01"]:
                # High volume excess stock approaching shelf-life cliff (60-67 days)
                current_usable = round(base_daily_demand * 28.0)
                near_cliff = round(current_usable * 0.35)  # 35% near-cliff!
                usable_gt_only = round(current_usable * 0.20)
                usable_mt_qc = current_usable - usable_gt_only
                avg_remaining_days = 63  # Near cliff!
            elif sku_id == "PR-GC" and depot_id == "Depot-North-01":
                # Shortage at North-01: 9 days of cover
                current_usable = round(base_daily_demand * 9.0)
                usable_mt_qc = round(current_usable * 0.85)
                usable_gt_only = current_usable - usable_mt_qc
                near_cliff = 0
                avg_remaining_days = 78
            elif sku_id == "PR-GC" and depot_id in ["Depot-South-01", "Depot-West-02"]:
                # Surplus at South-01: 29 days of cover
                current_usable = round(base_daily_demand * 29.0)
                usable_mt_qc = round(current_usable * 0.90)
                usable_gt_only = current_usable - usable_mt_qc
                near_cliff = round(current_usable * 0.08)
                avg_remaining_days = 75
            elif sku_id == "PR-PP" and depot_id == "Depot-North-01":
                # Shortage due to highway closure: 5.5 days cover
                current_usable = round(base_daily_demand * 5.5)
                usable_mt_qc = round(current_usable * 0.80)
                usable_gt_only = current_usable - usable_mt_qc
                near_cliff = 0
                avg_remaining_days = 74
            else:
                # Balanced / typical healthy depot: 18 - 24 days cover
                random_doc = np.random.uniform(18.0, 24.0)
                current_usable = round(base_daily_demand * random_doc)
                usable_mt_qc = round(current_usable * 0.85)
                usable_gt_only = current_usable - usable_mt_qc
                near_cliff = round(current_usable * 0.05)
                avg_remaining_days = int(np.random.randint(68, 85))
            
            lot_batch_id = f"LOT-{sku_id}-{depot_id[:7]}-B01"
            inventory_records.append({
                "sku_id": sku_id,
                "depot_id": depot_id,
                "usable_stock_mt_qc": usable_mt_qc,
                "usable_stock_gt_only": usable_gt_only,
                "near_cliff_stock": near_cliff,
                "total_usable_stock": current_usable,
                "lot_batch_id": lot_batch_id,
                "remaining_shelf_life_days": avg_remaining_days,
                "last_audit_date": base_date.strftime("%Y-%m-%d"),
                "is_synthetic": True,
            })
            
            # Forecast snapshots (Vintage W18 for next week forward evaluation)
            forecast_demand_daily = round(base_daily_demand * (viral_multiplier if sku_id == "PR-DP" else 1.0))
            naive_baseline_daily = round(base_daily_demand)  # repeats prior historical baseline
            
            forecast_records.append({
                "vintage_id": "VINTAGE-2026-W18",
                "snapshot_date": (base_date - datetime.timedelta(days=7)).strftime("%Y-%m-%d"),
                "target_date": base_date.strftime("%Y-%m-%d"),
                "sku_id": sku_id,
                "depot_id": depot_id,
                "forecast_demand": forecast_demand_daily,
                "naive_baseline_demand": naive_baseline_daily,
                "model_version": "Sensing-v1.4",
                "is_synthetic": True,
            })
            
            # Scheduled inbound shipments
            if depot_id in ["Depot-West-01", "Depot-North-01", "Depot-South-01"]:
                arrival_date = (base_date + datetime.timedelta(days=int(np.random.randint(2, 6)))).strftime("%Y-%m-%d")
                inbound_records.append({
                    "shipment_id": f"SHP-{sku_id}-{depot_id[-2:]}-01",
                    "sku_id": sku_id,
                    "destination_depot_id": depot_id,
                    "qty_bottles": round(base_daily_demand * 4.0),
                    "origin_type": "PLANT",
                    "origin_id": "Plant-West-01" if "West" in depot_id or "North" in depot_id else "Plant-South-01",
                    "dispatch_date": (base_date - datetime.timedelta(days=1)).strftime("%Y-%m-%d"),
                    "expected_arrival_date": arrival_date,
                    "actual_arrival_date": "",
                    "status": "IN_TRANSIT",
                    "is_on_time": True,
                    "is_in_full": True,
                })

    save_csv("demand_history", pd.DataFrame(demand_records))
    save_csv("inventory", pd.DataFrame(inventory_records))
    save_csv("forecast_snapshots", pd.DataFrame(forecast_records))
    save_csv("inbound_shipments", pd.DataFrame(inbound_records))
    
    # 5. Supplier Status & Disruptions
    supplier_data = [
        {
            "supplier_id": "SUPP-PASSION-01",
            "material_name": "Passionfruit Pulp",
            "origin_location": "Northeast Single Plantation Route",
            "transit_mode": "ROAD",
            "standard_lead_time_days": 3,
            "active_disruption_flag": True,
            "disruption_type": "HIGHWAY_CLOSURE",
            "effective_delay_days": 21,
            "notes": "NH closed for 3 weeks in May. No alternate road. Starting cover 14 days. Air freight contingency required (₹3.20 Cr).",
        },
        {
            "supplier_id": "SUPP-DRAGON-IMP",
            "material_name": "Imported Dragonfruit Pulp",
            "origin_location": "Vietnam Maritime Route",
            "transit_mode": "SEA",
            "standard_lead_time_days": 49,
            "active_disruption_flag": False,
            "disruption_type": "QUARTERLY_IMPORT_CYCLE",
            "effective_delay_days": 0,
            "notes": "40% imported dragonfruit pulp for PR-DB. 6-8 weeks quarterly lead time. Requires rigid forward booking.",
        },
        {
            "supplier_id": "SUPP-MANGO-01",
            "material_name": "Mango-Peach Blend",
            "origin_location": "Domestic Multi-Supplier",
            "transit_mode": "ROAD",
            "standard_lead_time_days": 4,
            "active_disruption_flag": False,
            "disruption_type": "NONE",
            "effective_delay_days": 0,
            "notes": "Healthy domestic supply. 38% summer volume share.",
        },
        {
            "supplier_id": "SUPP-GUAVA-01",
            "material_name": "Guava Pulp",
            "origin_location": "Domestic Multi-Supplier",
            "transit_mode": "ROAD",
            "standard_lead_time_days": 3,
            "active_disruption_flag": False,
            "disruption_type": "NONE",
            "effective_delay_days": 0,
            "notes": "Stable supply. Imbalance is purely finished-goods allocation across depots.",
        },
    ]
    save_csv("supplier_status", pd.DataFrame(supplier_data))
    
    # 6. Stockout Reports
    stockout_data = [
        {
            "report_id": "REP-2026-0518-01",
            "reported_at": "2026-05-18 10:30:00",
            "depot_id": "Depot-West-01",
            "sku_id": "PR-DP",
            "channel": "QC",
            "reported_by": "Depot Ops Lead - West",
            "evidence_source": "Blinkit/Zepto partner dark store stockout logs",
            "estimated_unmet_bottles": 28500,
            "notes": "Viral influencer video generated 4x surge. QC orders zeroed out across 18 dark stores.",
        },
        {
            "report_id": "REP-2026-0519-02",
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
    save_csv("stockout_reports", pd.DataFrame(stockout_data))
    
    # 7. Initial Pending Recommendation tickets
    # Pre-populate initial pending recommendations for the Control Tower / AI Copilot
    recs_data = [
        {
            "recommendation_id": "REC-2026-0520-001",
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
            "eta_days": 4,  # 3d transit + 1d approval
            "shelf_life_status": "PASS (76d remaining >= 67d gate)",
            "donor_post_cover_days": 23.5,  # Preserves >= 21d target
            "destination_post_cover_days": 8.5,
            "shortage_reduction_bottles": 18000,
            "status": "PENDING",
            "confidence_level": "HIGH",
            "diagnosis": "PR-DP @ Depot-West-01 facing stockout in 3.5 days from 4x QC velocity surge. Depot-South-02 has 32d cover and can safely donate 18,000 btls.",
            "is_synthetic": True,
        },
        {
            "recommendation_id": "REC-2026-0520-002",
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
            "donor_post_cover_days": 21.8,
            "destination_post_cover_days": 16.2,
            "shortage_reduction_bottles": 22000,
            "status": "PENDING",
            "confidence_level": "HIGH",
            "diagnosis": "PR-GC @ Depot-North-01 has 9.0d cover. Depot-South-01 holds 29.0d surplus.",
            "is_synthetic": True,
        },
        {
            "recommendation_id": "REC-2026-0520-003",
            "created_at": "2026-05-20 08:30:00",
            "priority": "P2",
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
            "confidence_level": "MEDIUM",
            "diagnosis": "Passionfruit highway disruption: Ration PR-PP by -30% to protect high-margin PR-DP contractual Modern Trade commitments.",
            "is_synthetic": True,
        },
    ]
    save_csv("recommendations", pd.DataFrame(recs_data))
    
    # Initial alarms
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
            "recommended_action": "Execute inter-depot rebalancing from Depot-South-02 (REC-2026-0520-001).",
            "recommendation_id": "REC-2026-0520-001",
            "acknowledged_by": None,
            "acknowledged_at": None,
            "resolved_at": None,
            "resolution_notes": None,
            "is_synthetic": True,
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
            "title": "Passionfruit Highway Closure (3 Weeks)",
            "description": "Northeast highway closure cuts 100% of passionfruit pulp road shipments. Plant cover at 14 days.",
            "observed_value": "14 days cover",
            "threshold_value": "21 days target",
            "source": "supplier_status",
            "confidence_level": "HIGH",
            "recommended_action": "Activate deterministic pulp rationing and evaluate emergency air freight contingency.",
            "recommendation_id": "REC-2026-0520-003",
            "acknowledged_by": None,
            "acknowledged_at": None,
            "resolved_at": None,
            "resolution_notes": None,
            "is_synthetic": True,
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
            "recommended_action": "Route immediately to General Trade via FEFO before reaching 60d rejection boundary.",
            "recommendation_id": None,
            "acknowledged_by": None,
            "acknowledged_at": None,
            "resolved_at": None,
            "resolution_notes": None,
            "is_synthetic": True,
        },
    ]
    save_csv("alarms", pd.DataFrame(alarms_data))


if __name__ == "__main__":
    generate_all_seed_data(force_regenerate=True)
    print("All seed data successfully generated in data/ folder.")
