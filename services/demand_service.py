"""Demand Intelligence & Censored-Demand Correction Service for RIOT RADAR.

Maintains distinct time series for:
1. Observed Sales
2. Censored Adjustment (Latent Demand Gap)
3. Corrected Demand (True Latent Demand)
4. Forecast Demand

Computes WAPE, Forecast Bias, Demand Uplift %, and Estimated Fill Rate %
with strict protection against zero-division errors.
"""

from typing import Dict, List, Optional, Tuple, Any
import numpy as np
import pandas as pd

from config.business_rules import (
    FRESHNESS_LAGS,
    HISTORICAL_FORECAST_ERROR_WAPE_PCT,
)
from services.csv_store import load_csv


def calculate_demand_uplift(observed: float, corrected: float) -> Optional[float]:
    """Calculate Demand Uplift % = (Corrected - Observed) / Observed * 100.
    
    Returns None if observed <= 0 to prevent infinity or division-by-zero errors.
    """
    if observed is None or observed <= 0:
        return None
    if corrected is None:
        return 0.0
    return ((corrected - observed) / observed) * 100.0


def calculate_service_level_fill_rate(
    fulfilled_demand: float,
    total_corrected_demand: float,
) -> Optional[float]:
    """Calculate Service Level (Fill Rate) = Fulfilled / Total Corrected * 100.
    
    Returns None if total_corrected_demand <= 0.
    """
    if total_corrected_demand is None or total_corrected_demand <= 0:
        return None
    if fulfilled_demand is None:
        return 0.0
    ratio = min(1.0, max(0.0, fulfilled_demand / total_corrected_demand))
    return ratio * 100.0


def calculate_wape(
    forecast: np.ndarray | List[float],
    actual: np.ndarray | List[float],
) -> Optional[float]:
    """Calculate Weighted Absolute Percentage Error (WAPE).
    
    WAPE = sum(|Forecast - Actual|) / sum(Actual) * 100.
    Returns None if sum(Actual) == 0.
    """
    f_arr = np.asarray(forecast, dtype=float)
    a_arr = np.asarray(actual, dtype=float)
    
    total_actual = np.sum(a_arr)
    if total_actual <= 0:
        return None
    
    total_abs_err = np.sum(np.abs(f_arr - a_arr))
    return float((total_abs_err / total_actual) * 100.0)


def calculate_forecast_bias(
    forecast: np.ndarray | List[float],
    actual: np.ndarray | List[float],
) -> Optional[float]:
    """Calculate Forecast Bias %.
    
    Forecast Bias = sum(Forecast - Actual) / sum(Actual) * 100.
    Positive = Overforecasting, Negative = Underforecasting.
    Returns None if sum(Actual) == 0.
    """
    f_arr = np.asarray(forecast, dtype=float)
    a_arr = np.asarray(actual, dtype=float)
    
    total_actual = np.sum(a_arr)
    if total_actual <= 0:
        return None
    
    total_diff = np.sum(f_arr - a_arr)
    return float((total_diff / total_actual) * 100.0)


class DemandService:
    """Service providing demand sensing, stockout censoring correction, and forecast evaluations."""

    def __init__(self):
        pass

    def get_demand_history(
        self,
        sku_id: Optional[str] = None,
        depot_id: Optional[str] = None,
        days: Optional[int] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """Fetch demand history records with type casting."""
        df = load_csv("demand_history")
        if df.empty:
            return df
            
        df["observed_sales"] = pd.to_numeric(df["observed_sales"], errors="coerce").fillna(0)
        df["censored_adjustment"] = pd.to_numeric(df["censored_adjustment"], errors="coerce").fillna(0)
        df["corrected_demand"] = pd.to_numeric(df["corrected_demand"], errors="coerce").fillna(0)
        df["freshness_lag_days"] = pd.to_numeric(df["freshness_lag_days"], errors="coerce").fillna(7)
        df["is_stockout_flagged"] = df["is_stockout_flagged"].astype(str).str.lower().isin(["true", "1"])
        
        if sku_id:
            df = df[df["sku_id"] == sku_id]
        if depot_id:
            df = df[df["depot_id"] == depot_id]
            
        # Sort by date
        df = df.sort_values("date")
        if start_date and end_date:
            df = df[(df["date"] >= start_date) & (df["date"] <= end_date)]
        elif start_date:
            df = df[df["date"] >= start_date]
        elif end_date:
            df = df[df["date"] <= end_date]
        elif days is not None and days > 0 and len(df) > 0:
            latest_date = df["date"].max()
            start_date_calc = (pd.to_datetime(latest_date) - pd.Timedelta(days=days)).strftime("%Y-%m-%d")
            df = df[df["date"] >= start_date_calc]
            
        return df

    def detect_and_correct_censored_demand(
        self,
        sku_id: str,
        depot_id: str,
        lookback_days: int = 14,
    ) -> Dict[str, Any]:
        """Detect censored demand and compute true latent demand estimate.
        
        Uses recent unconstrained daily velocity and active stockout reports.
        """
        df = self.get_demand_history(sku_id, depot_id, days=lookback_days)
        stockouts_df = load_csv("stockout_reports")
        
        has_manual_report = False
        reported_unmet = 0.0
        if not stockouts_df.empty:
            match = stockouts_df[
                (stockouts_df["sku_id"] == sku_id) & (stockouts_df["depot_id"] == depot_id)
            ]
            if not match.empty:
                has_manual_report = True
                reported_unmet = pd.to_numeric(match["estimated_unmet_bottles"], errors="coerce").sum()

        if df.empty:
            return {
                "sku_id": sku_id,
                "depot_id": depot_id,
                "observed_demand_sum": 0.0,
                "censored_adjustment_sum": 0.0,
                "corrected_demand_sum": 0.0,
                "demand_uplift_pct": None,
                "is_censored": False,
                "confidence": "LOW",
                "method": "NO_DATA",
            }

        unconstrained_days = df[~df["is_stockout_flagged"]]
        if len(unconstrained_days) >= 3:
            unconstrained_velocity = unconstrained_days["observed_sales"].mean()
        else:
            unconstrained_velocity = df["corrected_demand"].mean()

        total_observed = float(df["observed_sales"].sum())
        total_corrected = float(df["corrected_demand"].sum())
        total_adjustment = total_corrected - total_observed

        if has_manual_report and reported_unmet > 0 and total_adjustment <= 0:
            total_adjustment = float(reported_unmet)
            total_corrected = total_observed + total_adjustment

        is_censored = bool((df["is_stockout_flagged"].any()) or has_manual_report or (total_adjustment > 0))
        uplift_pct = calculate_demand_uplift(total_observed, total_corrected)

        return {
            "sku_id": sku_id,
            "depot_id": depot_id,
            "lookback_days": lookback_days,
            "observed_demand_sum": total_observed,
            "censored_adjustment_sum": total_adjustment,
            "corrected_demand_sum": total_corrected,
            "demand_uplift_pct": uplift_pct,
            "is_censored": is_censored,
            "unconstrained_daily_velocity": float(unconstrained_velocity),
            "manual_reported_unmet_bottles": float(reported_unmet),
            "confidence": "HIGH" if len(df) >= 7 else "MEDIUM",
            "method": "UNCONSTRAINED_VELOCITY_PLUS_DARKSTORE_LOGS",
            "is_synthetic": True,
        }

    def evaluate_forecast_vintage(
        self,
        vintage_id: str = "VINTAGE-2026-W18",
    ) -> Dict[str, Any]:
        """Evaluate saved forecast vintage against:
        1. Observed Sales
        2. Corrected Latent Demand
        3. Synthetic Ground Truth (demo-only)
        
        Compares RIOT RADAR sensing against the Naive Last-Week-Actual Benchmark.
        """
        f_df = load_csv("forecast_snapshots")
        d_df = self.get_demand_history(days=7)
        
        if f_df.empty or d_df.empty:
            return {
                "vintage_id": vintage_id,
                "wape_observed": None,
                "wape_corrected": None,
                "wape_naive_benchmark": None,
                "bias_pct": None,
                "status": "NO_EVALUATION_DATA",
            }
            
        f_sub = f_df[f_df["vintage_id"] == vintage_id].copy()
        if f_sub.empty:
            f_sub = f_df.copy()
            
        f_sub["forecast_demand"] = pd.to_numeric(f_sub["forecast_demand"], errors="coerce").fillna(0)
        f_sub["naive_baseline_demand"] = pd.to_numeric(f_sub["naive_baseline_demand"], errors="coerce").fillna(0)
        
        # Aggregate demand by SKU-Depot over latest 7 days
        grouped_d = d_df.groupby(["sku_id", "depot_id"]).agg({
            "observed_sales": "sum",
            "corrected_demand": "sum",
        }).reset_index()
        
        merged = pd.merge(f_sub, grouped_d, on=["sku_id", "depot_id"], how="inner")
        
        if merged.empty:
            return {
                "vintage_id": vintage_id,
                "wape_observed": None,
                "wape_corrected": None,
                "wape_naive_benchmark": None,
                "bias_pct": None,
                "status": "NO_OVERLAPPING_PERIODS",
            }
            
        # Scale daily forecast to 7-day period for apples-to-apples comparison
        forecast_7d = merged["forecast_demand"].to_numpy() * 7.0
        naive_7d = merged["naive_baseline_demand"].to_numpy() * 7.0
        observed_7d = merged["observed_sales"].to_numpy()
        corrected_7d = merged["corrected_demand"].to_numpy()
        
        wape_obs = calculate_wape(forecast_7d, observed_7d)
        wape_corr = calculate_wape(forecast_7d, corrected_7d)
        wape_naive = calculate_wape(naive_7d, corrected_7d)
        bias_corr = calculate_forecast_bias(forecast_7d, corrected_7d)
        
        return {
            "vintage_id": vintage_id,
            "sku_depots_evaluated": len(merged),
            "riot_radar_wape_corrected_pct": round(wape_corr, 1) if wape_corr is not None else None,
            "riot_radar_wape_observed_pct": round(wape_obs, 1) if wape_obs is not None else None,
            "naive_benchmark_wape_pct": round(wape_naive, 1) if wape_naive is not None else None,
            "forecast_bias_pct": round(bias_corr, 1) if bias_corr is not None else None,
            "historical_baseline_wape_pct": HISTORICAL_FORECAST_ERROR_WAPE_PCT,
            "accuracy_gain_pct": round(wape_naive - wape_corr, 1) if (wape_naive is not None and wape_corr is not None) else None,
            "is_synthetic_evaluation": True,
        }

    def get_national_vs_local_forecast_metrics(
        self,
        vintage_id: str = "VINTAGE-2026-W18",
    ) -> Dict[str, Any]:
        """Compute two-panel forecast evaluation:
        1. National Aggregate Panel: National WAPE & National aggregate Forecast Bias.
        2. SKU-Depot Disaggregated Panel: SKU-Depot WAPE & Mean Absolute SKU-Depot Bias.
        
        Demonstrates the aggregation fallacy: cancelling errors at national level hide severe local mismatches.
        """
        f_df = load_csv("forecast_snapshots")
        d_df = self.get_demand_history(days=7)

        if f_df.empty or d_df.empty:
            return {
                "vintage_id": vintage_id,
                "status": "NO_EVALUATION_DATA",
                "national_panel": {"wape_pct": None, "bias_pct": None},
                "sku_depot_panel": {"wape_pct": None, "mean_absolute_bias_pct": None},
            }

        f_sub = f_df[f_df["vintage_id"] == vintage_id].copy()
        if f_sub.empty:
            f_sub = f_df.copy()

        f_sub["forecast_demand"] = pd.to_numeric(f_sub["forecast_demand"], errors="coerce").fillna(0)
        grouped_d = d_df.groupby(["sku_id", "depot_id"]).agg({
            "observed_sales": "sum",
            "corrected_demand": "sum",
        }).reset_index()

        merged = pd.merge(f_sub, grouped_d, on=["sku_id", "depot_id"], how="inner")
        if merged.empty:
            return {
                "vintage_id": vintage_id,
                "status": "NO_OVERLAPPING_DATA",
                "national_panel": {"wape_pct": None, "bias_pct": None},
                "sku_depot_panel": {"wape_pct": None, "mean_absolute_bias_pct": None},
            }

        merged["f_7d"] = merged["forecast_demand"] * 7.0
        merged["a_7d"] = merged["corrected_demand"]

        nat_f = float(merged["f_7d"].sum())
        nat_a = float(merged["a_7d"].sum())

        # National Panel
        nat_wape = (abs(nat_f - nat_a) / nat_a * 100.0) if nat_a > 0 else 0.0
        nat_bias = ((nat_f - nat_a) / nat_a * 100.0) if nat_a > 0 else 0.0

        # SKU-Depot Panel
        total_abs_cell_error = float(np.sum(np.abs(merged["f_7d"].to_numpy() - merged["a_7d"].to_numpy())))
        sku_depot_wape = (total_abs_cell_error / nat_a * 100.0) if nat_a > 0 else 0.0

        # Compute cell bias for each of the 45 cells: (f - a) / a * 100
        # Strict rule: calculate mean absolute bias by taking the absolute value before averaging
        cell_biases = []
        for _, r in merged.iterrows():
            c_f = float(r["f_7d"])
            c_a = float(r["a_7d"])
            if c_a > 0:
                cell_bias = ((c_f - c_a) / c_a) * 100.0
            else:
                cell_bias = 0.0
            cell_biases.append(cell_bias)

        cell_biases_arr = np.array(cell_biases)
        mean_abs_bias = float(np.mean(np.abs(cell_biases_arr))) if len(cell_biases_arr) > 0 else 0.0
        signed_mean_bias = float(np.mean(cell_biases_arr)) if len(cell_biases_arr) > 0 else 0.0

        cancelling_gap = round(mean_abs_bias - abs(nat_bias), 2)

        # SKU-level breakdown across the 5 flavours
        sku_breakdown = []
        from config.business_rules import SKUS
        for sku_id, sku_meta in SKUS.items():
            sku_m = merged[merged["sku_id"] == sku_id]
            if sku_m.empty:
                continue
            s_f = float(sku_m["f_7d"].sum())
            s_a = float(sku_m["a_7d"].sum())
            s_wape = (abs(s_f - s_a) / s_a * 100.0) if s_a > 0 else 0.0
            s_bias = ((s_f - s_a) / s_a * 100.0) if s_a > 0 else 0.0
            s_cell_biases = np.array([
                ((float(r["f_7d"]) - float(r["a_7d"])) / float(r["a_7d"]) * 100.0)
                if float(r["a_7d"]) > 0 else 0.0
                for _, r in sku_m.iterrows()
            ])
            s_mean_abs_bias = float(np.mean(np.abs(s_cell_biases))) if len(s_cell_biases) > 0 else 0.0

            sku_breakdown.append({
                "sku_id": sku_id,
                "flavour": sku_meta.flavour,
                "national_wape_pct": round(s_wape, 1),
                "national_bias_pct": round(s_bias, 1),
                "mean_abs_depot_bias_pct": round(s_mean_abs_bias, 1),
                "cancelling_gap_pct": round(s_mean_abs_bias - abs(s_bias), 1),
            })

        return {
            "vintage_id": vintage_id,
            "evaluation_period": "7-day matching window vs latent corrected demand",
            "sku_depots_count": len(merged),
            "national_panel": {
                "wape_pct": round(nat_wape, 1),
                "bias_pct": round(nat_bias, 1),
                "bias_direction": "UNDERFORECASTING (-)" if nat_bias < 0 else "OVERFORECASTING (+)",
                "total_forecast_bottles": round(nat_f),
                "total_actual_bottles": round(nat_a),
            },
            "sku_depot_panel": {
                "wape_pct": round(sku_depot_wape, 1),
                "mean_absolute_bias_pct": round(mean_abs_bias, 1),
                "signed_mean_bias_pct": round(signed_mean_bias, 1),
                "cancelling_error_gap_pct": cancelling_gap,
            },
            "sku_breakdown": sku_breakdown,
            "aggregation_fallacy_note": (
                "National errors cancel across depots and SKUs. An aggregate national bias of "
                f"{round(nat_bias, 1)}% conceals a mean absolute SKU–Depot bias of {round(mean_abs_bias, 1)}%. "
                "Low national bias does not indicate accurate local forecasts."
            ),
            "data_honesty_note": (
                "Note: Evaluated on saved vintage snapshot VINTAGE-2026-W18 against 7-day corrected latent demand. "
                "Demonstration dataset calibrated to case constraints."
            ),
        }

    def get_sku_demand_mix(self) -> List[Dict[str, Any]]:
        """Calculate dynamic SKU portfolio demand mix across the summer dataset."""
        df = self.get_demand_history()
        if df.empty:
            return []
        
        from config.business_rules import SKUS
        sku_colors = {
            "PR-MPB": "#1863dc",
            "PR-GC": "#003c33",
            "PR-PP": "#d97706",
            "PR-DB": "#75758a",
            "PR-DP": "#b30000",
        }
        
        tot = float(df["corrected_demand"].sum())
        grouped = df.groupby("sku_id").agg({
            "corrected_demand": "sum",
            "observed_sales": "sum",
            "censored_adjustment": "sum",
        }).reset_index()
        
        results = []
        for _, r in grouped.iterrows():
            s_id = str(r["sku_id"])
            c_dem = float(r["corrected_demand"])
            o_dem = float(r["observed_sales"])
            share = round((c_dem / tot * 100.0), 1) if tot > 0 else 0.0
            sku_info = SKUS.get(s_id)
            flavour_name = sku_info.flavour if sku_info else s_id
            
            results.append({
                "sku_id": s_id,
                "name": f"{s_id} ({flavour_name})",
                "flavour": flavour_name,
                "value": share,
                "share_pct": share,
                "corrected_bottles": int(c_dem),
                "observed_bottles": int(o_dem),
                "censored_bottles": int(r["censored_adjustment"]),
                "revenue_cr": round((c_dem * 60.0) / 1e7, 2),
                "itemStyle": {"color": sku_colors.get(s_id, "#64748b")},
            })
            
        # Sort by share descending
        results.sort(key=lambda x: x["value"], reverse=True)
        return results

    def get_forecast_vintage_trajectory(self) -> Dict[str, Any]:
        """Compute chronological forecast performance trajectory across all weekly vintages (W09-W24)."""
        f_df = load_csv("forecast_snapshots")
        d_df = self.get_demand_history()
        
        if f_df.empty or d_df.empty:
            return {"labels": [], "wape_series": [], "bias_series": [], "naive_wape_series": [], "details": []}
            
        f_df["forecast_demand"] = pd.to_numeric(f_df["forecast_demand"], errors="coerce").fillna(0)
        f_df["naive_baseline_demand"] = pd.to_numeric(f_df["naive_baseline_demand"], errors="coerce").fillna(0)
        
        # Unique vintages sorted chronologically by snapshot_date
        v_order = f_df[["vintage_id", "snapshot_date", "target_date"]].drop_duplicates().sort_values("snapshot_date")
        
        labels = []
        wape_vals = []
        bias_vals = []
        naive_wape_vals = []
        details = []
        
        for _, v_row in v_order.iterrows():
            v_id = str(v_row["vintage_id"])
            targ = str(v_row["target_date"])
            snap = str(v_row["snapshot_date"])
            start = (pd.to_datetime(targ) - pd.Timedelta(days=6)).strftime("%Y-%m-%d")
            
            f_sub = f_df[f_df["vintage_id"] == v_id]
            d_sub = d_df[(d_df["date"] >= start) & (d_df["date"] <= targ)]
            
            if d_sub.empty:
                continue
                
            grouped_d = d_sub.groupby(["sku_id", "depot_id"]).agg({
                "corrected_demand": "sum",
                "observed_sales": "sum",
            }).reset_index()
            
            merged = pd.merge(f_sub, grouped_d, on=["sku_id", "depot_id"], how="inner")
            if merged.empty:
                continue
                
            f_7d = merged["forecast_demand"].to_numpy() * 7.0
            n_7d = merged["naive_baseline_demand"].to_numpy() * 7.0
            c_7d = merged["corrected_demand"].to_numpy()
            
            wape = calculate_wape(f_7d, c_7d)
            naive_wape = calculate_wape(n_7d, c_7d)
            bias = calculate_forecast_bias(f_7d, c_7d)
            
            # Short label e.g. "W18"
            w_label = v_id.split("-")[-1] if "-W" in v_id else v_id
            if v_id == "VINTAGE-2026-W18":
                w_label = f"{w_label} (Current)"
                
            wape_round = round(wape, 1) if wape is not None else 0.0
            bias_round = round(bias, 1) if bias is not None else 0.0
            naive_round = round(naive_wape, 1) if naive_wape is not None else 0.0
            
            labels.append(w_label)
            wape_vals.append(wape_round)
            bias_vals.append(bias_round)
            naive_wape_vals.append(naive_round)
            
            details.append({
                "vintage_id": v_id,
                "label": w_label,
                "snapshot_date": snap,
                "target_date": targ,
                "wape_pct": wape_round,
                "naive_wape_pct": naive_round,
                "bias_pct": bias_round,
            })
            
        return {
            "labels": labels,
            "wape_series": wape_vals,
            "bias_series": bias_vals,
            "naive_wape_series": naive_wape_vals,
            "details": details,
        }

