"""Distribution Optimization & 45 SKU–Depot Operational Service for RIOT RADAR.

Maintains the complete 45 SKU–Depot operational grain with all 22 derived measures.
Calculates allocation gaps, compares historical vs demand-driven allocations,
and generates feasible, non-duplicate inter-depot rebalancing proposals.
"""

from typing import Dict, List, Optional, Any, Tuple
import datetime
import numpy as np
import pandas as pd

from config.business_rules import (
    SKUS,
    DEPOTS,
    DEFAULT_TARGET_COVER_DAYS,
    DEFAULT_APPROVAL_LATENCY_DAYS,
    TRANSFER_COST_PER_BOTTLE_INR,
    NEAR_CLIFF_WARNING_DAYS,
    MT_QC_MIN_SHELF_LIFE_DAYS,
    RISK_THRESHOLDS,
)
from services.csv_store import load_csv, save_csv, append_csv_row
from services.demand_service import (
    DemandService,
    calculate_demand_uplift,
    calculate_service_level_fill_rate,
    calculate_wape,
    calculate_forecast_bias,
)
from services.inventory_service import (
    InventoryService,
    calculate_days_of_cover,
    calculate_target_stock,
    calculate_allocation_gap,
)


def get_inter_depot_transit_days(orig_id: str, dest_id: str) -> int:
    """Calculate inter-depot transit days strictly from configured depot regions and lead times."""
    orig_depot = next((d for d in DEPOTS if d["depot_id"] == orig_id), None)
    dest_depot = next((d for d in DEPOTS if d["depot_id"] == dest_id), None)
    if not orig_depot or not dest_depot:
        return 3

    orig_reg = orig_depot.get("region", "")
    dest_reg = dest_depot.get("region", "")

    # Intra-regional transit (e.g., Delhi NCR <-> Lucknow)
    if orig_reg == dest_reg:
        return 2

    # Adjacent regional corridors
    adjacent_pairs = {
        ("North", "Central"), ("Central", "North"),
        ("West", "Central"), ("Central", "West"),
        ("South", "Central"), ("Central", "South"),
        ("East", "Central"), ("Central", "East"),
        ("North", "West"), ("West", "North"),
    }
    if (orig_reg, dest_reg) in adjacent_pairs:
        return 3

    # Cross-country long-haul (e.g., South <-> North, West <-> East)
    return 4


class DistributionService:
    """Service for the 45 SKU–Depot grid, allocation gap calculation, and inter-depot transfer optimization."""

    def __init__(self):
        self.demand_service = DemandService()
        self.inventory_service = InventoryService()

    def get_45_sku_depot_grid(
        self,
        target_cover_days: float = DEFAULT_TARGET_COVER_DAYS,
        forecast_vintage_id: str = "VINTAGE-2026-W18",
    ) -> pd.DataFrame:
        """Construct the authoritative 45 SKU–Depot operational table with all 22 required fields."""
        demand_hist = self.demand_service.get_demand_history(days=7)
        inv_df = self.inventory_service.get_inventory_table()
        forecasts = load_csv("forecast_snapshots")
        inbounds = load_csv("inbound_shipments")
        recs_df = load_csv("recommendations")

        # Active transfers pending or approved
        active_recs = pd.DataFrame()
        if not recs_df.empty:
            active_recs = recs_df[recs_df["status"].isin(["PENDING", "APPROVED"])]

        rows = []
        for sku_id, sku in SKUS.items():
            for depot in DEPOTS:
                depot_id = depot["depot_id"]

                # 1 & 2 & 3. Demand numbers
                sku_depot_demand = demand_hist[
                    (demand_hist["sku_id"] == sku_id) & (demand_hist["depot_id"] == depot_id)
                ]
                obs_demand = float(sku_depot_demand["observed_sales"].sum()) if not sku_depot_demand.empty else 0.0
                corr_demand = float(sku_depot_demand["corrected_demand"].sum()) if not sku_depot_demand.empty else 0.0
                cens_adj = corr_demand - obs_demand

                # 4. Demand Uplift % (safe zero handling)
                uplift_pct = calculate_demand_uplift(obs_demand, corr_demand)

                # 5 & 6. Forecast Demand & Vintage ID
                daily_forecast = 0.0
                if not forecasts.empty:
                    f_match = forecasts[
                        (forecasts["vintage_id"] == forecast_vintage_id)
                        & (forecasts["sku_id"] == sku_id)
                        & (forecasts["depot_id"] == depot_id)
                    ]
                    if not f_match.empty:
                        daily_forecast = float(f_match.iloc[0]["forecast_demand"])
                if daily_forecast <= 0 and not sku_depot_demand.empty:
                    daily_forecast = float(sku_depot_demand["corrected_demand"].mean())

                # 7 & 8. Inventory breakdown
                sku_depot_inv = inv_df[
                    (inv_df["sku_id"] == sku_id) & (inv_df["depot_id"] == depot_id)
                ]
                usable_mt_qc = float(sku_depot_inv.iloc[0]["usable_stock_mt_qc"]) if not sku_depot_inv.empty else 0.0
                usable_gt_only = float(sku_depot_inv.iloc[0]["usable_stock_gt_only"]) if not sku_depot_inv.empty else 0.0
                total_usable = float(sku_depot_inv.iloc[0]["total_usable_stock"]) if not sku_depot_inv.empty else 0.0
                rem_shelf_days = float(sku_depot_inv.iloc[0]["remaining_shelf_life_days"]) if not sku_depot_inv.empty else 90.0

                # 9 & 10. Inbound Qty & OTIF Status
                inbound_qty = 0.0
                otif_status = "ON_TIME"
                if not inbounds.empty:
                    inb_match = inbounds[
                        (inbounds["sku_id"] == sku_id)
                        & (inbounds["destination_depot_id"] == depot_id)
                        & (inbounds["status"] == "IN_TRANSIT")
                    ]
                    if not inb_match.empty:
                        inbound_qty = float(pd.to_numeric(inb_match["qty_bottles"], errors="coerce").sum())
                        if not inb_match["is_on_time"].all():
                            otif_status = "DELAYED"

                # 11 & 12. Target stock & Allocation gap
                target_stock = calculate_target_stock(daily_forecast, target_cover_days)
                alloc_gap = calculate_allocation_gap(target_stock, total_usable + inbound_qty)

                # 13 & 14. Days of Cover & Projected stockout date
                doc = calculate_days_of_cover(total_usable, daily_forecast)
                proj_stockout = self.inventory_service.get_projected_stockout_date(sku_id, depot_id, daily_forecast)

                # 15 & 16. Proposed transfers in/out
                transfer_in_qty = 0.0
                transfer_out_qty = 0.0
                if not active_recs.empty:
                    in_recs = active_recs[
                        (active_recs["sku_id"] == sku_id)
                        & (active_recs["destination_depot_id"] == depot_id)
                    ]
                    out_recs = active_recs[
                        (active_recs["sku_id"] == sku_id)
                        & (active_recs["origin_depot_id"] == depot_id)
                    ]
                    if not in_recs.empty:
                        transfer_in_qty = float(pd.to_numeric(in_recs["quantity_bottles"], errors="coerce").sum())
                    if not out_recs.empty:
                        transfer_out_qty = float(pd.to_numeric(out_recs["quantity_bottles"], errors="coerce").sum())

                # 17 & 18. Transfer cost & ETA days
                transfer_cost = (transfer_in_qty + transfer_out_qty) * TRANSFER_COST_PER_BOTTLE_INR
                transit_days = depot.get("lead_time_days", 3)
                eta_days = transit_days + DEFAULT_APPROVAL_LATENCY_DAYS

                # 19 & 20. WAPE & Bias (for this SKU-Depot over 7d)
                wape_val = None
                bias_val = None
                if not sku_depot_demand.empty and daily_forecast > 0:
                    f_arr = np.full(len(sku_depot_demand), daily_forecast)
                    a_arr = sku_depot_demand["corrected_demand"].to_numpy()
                    wape_val = calculate_wape(f_arr, a_arr)
                    bias_val = calculate_forecast_bias(f_arr, a_arr)

                # 21. Confidence level
                conf_level = "HIGH" if len(sku_depot_demand) >= 7 else "MEDIUM"

                # 22. Service level (fill rate %)
                fulfilled = min(total_usable, corr_demand)
                fill_rate = calculate_service_level_fill_rate(fulfilled, corr_demand)

                rows.append({
                    "sku_id": sku_id,
                    "flavour": sku.flavour,
                    "depot_id": depot_id,
                    "depot_name": depot["name"],
                    "region": depot["region"],
                    "observed_demand": round(obs_demand),
                    "censored_adjustment": round(cens_adj),
                    "corrected_demand": round(corr_demand),
                    "demand_uplift_pct": round(uplift_pct, 1) if uplift_pct is not None else None,
                    "forecast_demand": round(daily_forecast),
                    "forecast_vintage_id": forecast_vintage_id,
                    "usable_stock_mt_qc": round(usable_mt_qc),
                    "usable_stock_gt_only": round(usable_gt_only),
                    "total_usable_stock": round(total_usable),
                    "remaining_shelf_life_days": round(rem_shelf_days),
                    "inbound_qty": round(inbound_qty),
                    "otif_status": otif_status,
                    "target_stock": round(target_stock),
                    "allocation_gap": round(alloc_gap),
                    "days_of_cover": round(doc, 1) if doc is not None else None,
                    "projected_stockout_date": proj_stockout if proj_stockout else "NONE (>21d)",
                    "proposed_transfer_in_qty": round(transfer_in_qty),
                    "proposed_transfer_out_qty": round(transfer_out_qty),
                    "transfer_cost_inr": round(transfer_cost),
                    "eta_days": eta_days,
                    "wape_pct": round(wape_val, 1) if wape_val is not None else None,
                    "forecast_bias_pct": round(bias_val, 1) if bias_val is not None else None,
                    "confidence_level": conf_level,
                    "service_level_fill_rate_pct": round(fill_rate, 1) if fill_rate is not None else None,
                    "is_synthetic": True,
                })

        return pd.DataFrame(rows)

    def optimize_inter_depot_rebalancing(
        self,
        sku_id: Optional[str] = None,
        target_cover_days: float = DEFAULT_TARGET_COVER_DAYS,
    ) -> List[Dict[str, Any]]:
        """Generate feasibility-ranked inter-depot transfer recommendations.
        
        Strict Feasibility Constraints:
        1. Donor must retain >= 21 days target cover after transfer.
        2. Channel eligibility check:
           - Stock with remaining shelf life < 67 days is blocked for MT/QC transfers.
           - Stock < 60 days is GT-only restricted.
        3. Effective ETA = transit time + 1 day approval latency.
        4. Transfer cost = quantity * ₹1.50.
        5. Proximity & Feasibility Ranking:
           - Evaluates all potential donor candidates for each shortage depot.
           - Ranks candidates by feasibility, lowest transit lead time (e.g. Lucknow for NCR),
             and surplus volume while protecting donor cover.
           - Documents why selected donor was chosen and why alternatives were rejected.
        6. Deduplication: does not propose redundant transfers if one is already active.
        """
        grid_df = self.get_45_sku_depot_grid(target_cover_days=target_cover_days)
        recs_df = load_csv("recommendations")
        
        # Check active recommendations to avoid duplicate proposals
        existing_keys = set()
        if not recs_df.empty:
            for _, r in recs_df[recs_df["status"].isin(["PENDING", "APPROVED"])].iterrows():
                key = (r["sku_id"], r["origin_depot_id"], r["destination_depot_id"])
                existing_keys.add(key)

        skus_to_check = [sku_id] if sku_id else list(SKUS.keys())
        proposals = []

        for curr_sku in skus_to_check:
            sku_sub = grid_df[grid_df["sku_id"] == curr_sku].copy()

            # Shortage depots: allocation_gap > 1000 and days_of_cover < 14.0
            shortage_depots = sku_sub[
                (sku_sub["allocation_gap"] > 1000) & (sku_sub["days_of_cover"] < 14.0)
            ].sort_values("days_of_cover")

            # All potential donor depots with stock
            all_candidate_depots = sku_sub[sku_sub["days_of_cover"] > 14.0].copy()

            for _, dest_row in shortage_depots.iterrows():
                dest_id = dest_row["depot_id"]
                dest_name = dest_row["depot_name"]
                dest_deficit = float(dest_row["allocation_gap"])
                dest_doc_before = float(dest_row["days_of_cover"]) if dest_row["days_of_cover"] else 0.0
                dest_daily_burn = float(dest_row["forecast_demand"])

                # Evaluate all candidate donors for this shortage depot
                candidate_evals = []

                for _, orig_row in all_candidate_depots.iterrows():
                    orig_id = orig_row["depot_id"]
                    if orig_id == dest_id:
                        continue

                    orig_name = orig_row["depot_name"]
                    orig_stock = float(orig_row["total_usable_stock"])
                    orig_daily_burn = float(orig_row["forecast_demand"])
                    orig_shelf_life = float(orig_row["remaining_shelf_life_days"])
                    orig_doc = float(orig_row["days_of_cover"]) if orig_row["days_of_cover"] else 0.0

                    # Transit lead time strictly based on configured depot regions
                    transit_days = get_inter_depot_transit_days(orig_id, dest_id)
                    effective_eta = transit_days + DEFAULT_APPROVAL_LATENCY_DAYS

                    # Rule 1: Donor must retain >= 21 days cover
                    orig_required_stock = orig_daily_burn * DEFAULT_TARGET_COVER_DAYS
                    max_releasable = max(0.0, orig_stock - orig_required_stock)

                    # Shelf-life check
                    if orig_shelf_life < MT_QC_MIN_SHELF_LIFE_DAYS:
                        shelf_elig = "GT_ONLY (<60d)"
                        shelf_ok = False
                        shelf_reason = "Fails MT/QC threshold (<60d remaining)"
                    elif orig_shelf_life <= NEAR_CLIFF_WARNING_DAYS:
                        shelf_elig = "WARNING_NEAR_CLIFF (60-67d)"
                        shelf_ok = True
                        shelf_reason = "Near-cliff stock: route via fast transit"
                    else:
                        shelf_elig = "ALL_CHANNELS (>=67d)"
                        shelf_ok = True
                        shelf_reason = "Satisfies >=67d MT/QC gate"

                    # Feasibility logic
                    is_feasible = True
                    rejection_reason = None

                    if max_releasable < 1000:
                        is_feasible = False
                        rejection_reason = f"Safety cover breach: surplus is {int(max_releasable):,} btls (<1,000 btls required to retain >=21d cover)"
                    elif not shelf_ok:
                        is_feasible = False
                        rejection_reason = f"Shelf-life cliff: {shelf_reason}"
                    elif (curr_sku, orig_id, dest_id) in existing_keys:
                        is_feasible = False
                        rejection_reason = "Duplicate transfer proposal already active"

                    # Rank score: feasible first, then lowest transit days, then highest surplus
                    rank_score = (0 if is_feasible else 100) + (transit_days * 10) - (max_releasable / 10000.0)

                    candidate_evals.append({
                        "depot_id": orig_id,
                        "depot_name": orig_name,
                        "region": orig_row["region"],
                        "transit_days": transit_days,
                        "eta_days": effective_eta,
                        "surplus_releasable_bottles": int(max_releasable),
                        "donor_cover_days": round(orig_doc, 1),
                        "shelf_life_days": int(orig_shelf_life),
                        "channel_eligibility": shelf_elig,
                        "is_feasible": is_feasible,
                        "rejection_reason": rejection_reason,
                        "rank_score": rank_score,
                        "orig_row": orig_row,
                    })

                # Sort evaluated candidates: best feasible candidates first
                candidate_evals.sort(key=lambda x: x["rank_score"])

                # Select best feasible candidate donors
                for cand in candidate_evals:
                    if not cand["is_feasible"]:
                        continue

                    orig_row = cand["orig_row"]
                    orig_id = cand["depot_id"]
                    orig_stock = float(orig_row["total_usable_stock"])
                    orig_daily_burn = float(orig_row["forecast_demand"])
                    orig_shelf_life = float(orig_row["remaining_shelf_life_days"])
                    max_releasable = float(cand["surplus_releasable_bottles"])

                    transfer_qty = min(dest_deficit, max_releasable)
                    transfer_qty = round(transfer_qty / 500) * 500  # Pallet batches of 500
                    if transfer_qty <= 0:
                        continue

                    transit_days = cand["transit_days"]
                    effective_eta_days = cand["eta_days"]

                    if orig_shelf_life < MT_QC_MIN_SHELF_LIFE_DAYS:
                        shelf_status = "GT_ONLY_ELIGIBLE (<60d)"
                        channel_eligible = "GT"
                    elif orig_shelf_life <= NEAR_CLIFF_WARNING_DAYS:
                        shelf_status = f"WARNING_NEAR_CLIFF ({int(orig_shelf_life)}d remaining: restricted to GT)"
                        channel_eligible = "GT"
                    else:
                        shelf_status = f"PASS ({int(orig_shelf_life)}d remaining >= 67d MT/QC gate)"
                        channel_eligible = "ALL_CHANNELS (MT, QC, GT)"

                    donor_post_cover = calculate_days_of_cover(
                        orig_stock - transfer_qty, orig_daily_burn
                    )
                    dest_post_cover = calculate_days_of_cover(
                        float(dest_row["total_usable_stock"]) + transfer_qty, dest_daily_burn
                    )

                    cost_inr = transfer_qty * TRANSFER_COST_PER_BOTTLE_INR
                    protected_contrib_inr = transfer_qty * 60.0 * 0.32

                    # Alternatives summary for planner transparency
                    other_rejections = [
                        f"{c['depot_name']}: {c['rejection_reason'] or 'Higher transit lead time (' + str(c['transit_days']) + 'd)'}"
                        for c in candidate_evals if c["depot_id"] != orig_id
                    ]
                    alternatives_note = "; ".join(other_rejections[:2]) if other_rejections else "No alternative donors available."

                    rec_id = f"REC-{datetime.datetime.now().strftime('%m%d')}-{len(proposals)+1:03d}"
                    proposal = {
                        "recommendation_id": rec_id,
                        "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "priority": "P1" if dest_doc_before < 7.0 else "P2",
                        "module": "DISTRIBUTION",
                        "sku_id": curr_sku,
                        "flavour": SKUS[curr_sku].flavour,
                        "origin_depot_id": orig_id,
                        "destination_depot_id": dest_id,
                        "action_type": "INTER_DEPOT_TRANSFER",
                        "quantity_bottles": int(transfer_qty),
                        "cost_inr": float(cost_inr),
                        "protected_contribution_inr": float(protected_contrib_inr),
                        "lead_time_days": transit_days,
                        "eta_days": effective_eta_days,
                        "shelf_life_status": shelf_status,
                        "channel_eligibility": channel_eligible,
                        "donor_cover_before_days": round(float(orig_row["days_of_cover"]), 1),
                        "donor_post_cover_days": round(donor_post_cover, 1) if donor_post_cover else None,
                        "destination_cover_before_days": round(dest_doc_before, 1),
                        "destination_post_cover_days": round(dest_post_cover, 1) if dest_post_cover else None,
                        "shortage_reduction_bottles": int(transfer_qty),
                        "status": "PENDING",
                        "confidence_level": "HIGH",
                        "selection_rationale": (
                            f"Selected {cand['depot_name']} as lowest transit lead time feasible donor ({transit_days}d transit). "
                            f"Releases {int(transfer_qty):,} btls while safely maintaining {donor_post_cover:.1f}d post-cover (>=21d target)."
                        ),
                        "rejected_alternatives": alternatives_note,
                        "candidates_evaluated": [
                            {
                                "depot_id": c["depot_id"],
                                "depot_name": c["depot_name"],
                                "region": c["region"],
                                "transit_days": c["transit_days"],
                                "surplus_bottles": c["surplus_releasable_bottles"],
                                "is_feasible": c["is_feasible"],
                                "rejection_reason": c["rejection_reason"],
                                "status": "SELECTED" if c["depot_id"] == orig_id else ("BACKUP" if c["is_feasible"] else "REJECTED"),
                            }
                            for c in candidate_evals
                        ],
                        "diagnosis": (
                            f"{curr_sku} @ {dest_name} cover is {dest_doc_before:.1f}d (Target 21d). "
                            f"{cand['depot_name']} has surplus {float(orig_row['days_of_cover']):.1f}d and can release {int(transfer_qty):,} btls."
                        ),
                        "is_synthetic": True,
                    }
                    proposals.append(proposal)
                    existing_keys.add((curr_sku, orig_id, dest_id))
                    dest_deficit -= transfer_qty
                    if dest_deficit <= 1000:
                        break

        return proposals

    def get_allocation_alignment_report(self) -> Dict[str, Any]:
        """Compute Alignment Index across all 5 SKUs comparing:
        1. Historical-mix allocation vs Corrected demand.
        2. Current operational allocation vs Corrected demand.
        3. Post-rebalancing intervention allocation vs Corrected demand (same demand assumptions).
        """
        grid = self.get_45_sku_depot_grid()
        sku_reports = []

        # Standard historical capacity allocation weights (pre-surge legacy weights)
        historical_weights = {
            "Depot-North-01": 0.12, "Depot-North-02": 0.09, "Depot-North-03": 0.07,
            "Depot-West-01": 0.14, "Depot-West-02": 0.11, "Depot-Central-01": 0.08,
            "Depot-South-01": 0.17, "Depot-South-02": 0.14, "Depot-East-01": 0.08,
        }

        for sku_id, sku_meta in SKUS.items():
            sku_rows = grid[grid["sku_id"] == sku_id]
            if sku_rows.empty:
                continue

            demand_by_depot = {}
            current_alloc_by_depot = {}
            historical_alloc_by_depot = {}
            post_rebal_alloc_by_depot = {}

            total_sku_stock = float(sku_rows["total_usable_stock"].sum())

            for _, row in sku_rows.iterrows():
                d_id = row["depot_id"]
                curr_stock = float(row["total_usable_stock"])
                corr_demand = float(row["corrected_demand"])
                net_transfer = float(row["proposed_transfer_in_qty"]) - float(row["proposed_transfer_out_qty"])

                demand_by_depot[d_id] = corr_demand
                current_alloc_by_depot[d_id] = curr_stock
                historical_alloc_by_depot[d_id] = total_sku_stock * historical_weights.get(d_id, 1.0 / 9.0)
                post_rebal_alloc_by_depot[d_id] = max(0.0, curr_stock + net_transfer)

            # Historical mix vs Demand
            hist_res = calculate_allocation_alignment_index(historical_alloc_by_depot, demand_by_depot)
            # Current operational allocation vs Demand
            curr_res = calculate_allocation_alignment_index(current_alloc_by_depot, demand_by_depot)
            # Post-intervention allocation vs Demand (using identical demand assumptions)
            post_res = calculate_allocation_alignment_index(post_rebal_alloc_by_depot, demand_by_depot)

            sku_reports.append({
                "sku_id": sku_id,
                "flavour": sku_meta.flavour,
                "historical_mix_index_pct": hist_res["alignment_index_pct"],
                "current_allocation_index_pct": curr_res["alignment_index_pct"],
                "post_intervention_index_pct": post_res["alignment_index_pct"],
                "improvement_pct": round(curr_res["alignment_index_pct"] - post_res["alignment_index_pct"], 2),
                "historical_depot_breakdown": hist_res["depot_breakdown"],
                "current_depot_breakdown": curr_res["depot_breakdown"],
                "post_intervention_depot_breakdown": post_res["depot_breakdown"],
            })

        return {
            "sku_alignment_indices": sku_reports,
            "metric_name": "Allocation-Mismatch Index",
            "metric_definition": "Σ |Allocation Share - Demand Share| / 2 (0% = perfect alignment, lower is better)",
            "data_honesty_note": "Evaluated against 7-day corrected latent demand using identical demand assumptions across before and after states.",
        }


def calculate_allocation_alignment_index(
    allocation_by_depot: Dict[str, float],
    demand_by_depot: Dict[str, float],
) -> Dict[str, Any]:
    """Calculate Allocation-vs-Demand Alignment (Mismatch) Index across depots.

    Formula:
    Allocation share at depot = Depot allocated quantity / National allocated quantity
    Corrected demand share at depot = Depot corrected demand / National corrected demand
    Alignment Index = Σ |Allocation share - Corrected demand share| / 2

    Returns:
    - alignment_index_pct: Float percentage between 0.0% and 100.0%. Lower is better (0% = perfect match).
    - depot_breakdown: List of per-depot breakdown with allocation share, demand share, and mismatch contribution.
    """
    total_alloc = sum(max(0.0, float(v)) for v in allocation_by_depot.values())
    total_demand = sum(max(0.0, float(v)) for v in demand_by_depot.values())

    all_depots = sorted(list(set(list(allocation_by_depot.keys()) + list(demand_by_depot.keys()))))
    if not all_depots:
        return {
            "alignment_index_pct": 0.0,
            "total_allocated": 0.0,
            "total_demand": 0.0,
            "depot_breakdown": [],
            "status": "NO_DEPOTS",
        }

    if total_alloc <= 0.0 or total_demand <= 0.0:
        return {
            "alignment_index_pct": 0.0,
            "total_allocated": total_alloc,
            "total_demand": total_demand,
            "depot_breakdown": [
                {
                    "depot_id": d,
                    "allocated_qty": float(allocation_by_depot.get(d, 0.0)),
                    "demand_qty": float(demand_by_depot.get(d, 0.0)),
                    "allocation_share_pct": 0.0,
                    "demand_share_pct": 0.0,
                    "mismatch_contribution_pct": 0.0,
                }
                for d in all_depots
            ],
            "status": "ZERO_TOTAL_SUPPLY_OR_DEMAND",
        }

    depot_breakdown = []
    total_abs_diff = 0.0

    for d in all_depots:
        alloc_qty = max(0.0, float(allocation_by_depot.get(d, 0.0)))
        demand_qty = max(0.0, float(demand_by_depot.get(d, 0.0)))

        alloc_share = alloc_qty / total_alloc
        demand_share = demand_qty / total_demand

        diff = abs(alloc_share - demand_share)
        contrib = diff / 2.0
        total_abs_diff += diff

        depot_breakdown.append({
            "depot_id": d,
            "allocated_qty": round(alloc_qty),
            "demand_qty": round(demand_qty),
            "allocation_share_pct": round(alloc_share * 100.0, 2),
            "demand_share_pct": round(demand_share * 100.0, 2),
            "mismatch_contribution_pct": round(contrib * 100.0, 2),
        })

    index_pct = round((total_abs_diff / 2.0) * 100.0, 2)

    return {
        "alignment_index_pct": index_pct,
        "total_allocated": round(total_alloc),
        "total_demand": round(total_demand),
        "depot_breakdown": depot_breakdown,
        "status": "CALCULATED",
    }
