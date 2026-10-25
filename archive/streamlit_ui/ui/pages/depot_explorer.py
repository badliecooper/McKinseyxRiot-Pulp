"""Page 2 — Depot Explorer for RIOT RADAR.

Provides deep regional and SKU-level operational diagnostics:
- Depot selector (9 depots) and SKU selector (5 finished goods)
- Exactly five primary local KPIs (DoC, Allocation Gap, Demand Uplift %, Forecast Bias %, Estimated Fill Rate %)
- Chart 7: Demand Sensing vs. Forecast Time Series
- Chart 8: Projected Inventory Depletion & Cover Timeline (with 60d/67d shelf-life gates)
- Rebalancing action controls with inline approval workflow
- Manual Stock-Out Reporting form logging to stockout_reports.csv
"""

import datetime
import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np

import tools
import approval
from config.business_rules import (
    COLOR_TOKENS,
    SKUS,
    DEPOTS,
    DEFAULT_TARGET_COVER_DAYS,
    NEAR_CLIFF_WARNING_DAYS,
    MT_QC_MIN_SHELF_LIFE_DAYS,
)
from services.csv_store import append_csv_row, load_csv
from ui.components.theme import style_scm_figure


def render_depot_explorer():
    st.markdown("### [RIOT RADAR] Depot Explorer — Local SKU–Depot Diagnostics")
    st.caption("Granular daily demand sensing, shelf-life channel allocation, and depletion projections.")

    # --------------------------------------------------------------------------
    # TOP SELECTORS: DEPOT & SKU
    # --------------------------------------------------------------------------
    col_d, col_s = st.columns(2)
    with col_d:
        depot_ids = [d["depot_id"] for d in DEPOTS]
        selected_depot = st.selectbox(
            "Select Regional Depot (1 of 9)",
            depot_ids,
            index=2,  # Default to Depot-West-01 (Mumbai)
            key="depot_selector",
        )
    with col_s:
        sku_ids = list(SKUS.keys())
        selected_sku = st.selectbox(
            "Select Finished Goods SKU (1 of 5)",
            sku_ids,
            index=4,  # Default to PR-DP (Dragon Passion)
            key="sku_selector",
        )

    # Fetch 45-grid record for selected combination
    grid_df = tools.get_sku_depot_grid()
    record = grid_df[(grid_df["depot_id"] == selected_depot) & (grid_df["sku_id"] == selected_sku)]
    if record.empty:
        st.warning("Selected SKU–Depot combination not found in current operational grain.")
        return

    rec = record.iloc[0]

    # --------------------------------------------------------------------------
    # FIVE PRIMARY LOCAL KPIS
    # --------------------------------------------------------------------------
    st.markdown("<div style='margin-top:10px;'></div>", unsafe_allow_html=True)
    k1, k2, k3, k4, k5 = st.columns(5)

    doc_val = rec["days_of_cover"]
    doc_str = f"{doc_val:.1f} Days" if doc_val is not None else "N/A"
    doc_color = "normal" if (doc_val and doc_val >= 14) else "inverse"
    k1.metric("Days of Cover (DoC)", doc_str, delta=f"Target: {DEFAULT_TARGET_COVER_DAYS}d", delta_color=doc_color)

    gap_val = rec["allocation_gap"]
    gap_str = f"{gap_val:,} btls"
    k2.metric("Allocation Gap", gap_str, help="Target Stock required minus projected usable inventory")

    uplift_val = rec["demand_uplift_pct"]
    uplift_str = f"+{uplift_val:.1f}%" if uplift_val is not None else "N/A"
    k3.metric("Demand Uplift %", uplift_str, help="(Corrected Demand - Observed Demand) / Observed Demand * 100")

    bias_val = rec["forecast_bias_pct"]
    bias_str = f"{bias_val:+.1f}%" if bias_val is not None else "0.0%"
    k4.metric("Forecast Bias %", bias_str, help="Systematic over/underforecast (+: over, -: under)")

    fill_val = rec["service_level_fill_rate_pct"]
    fill_str = f"{fill_val:.1f}%" if fill_val is not None else "N/A"
    k5.metric("Estimated Fill Rate %", fill_str, help="Fulfilled Demand / Total Estimated Corrected Demand")

    st.markdown("<div style='margin-top:14px;'></div>", unsafe_allow_html=True)

    # --------------------------------------------------------------------------
    # CHARTS: DEMAND SENSING (CHART 7) & INVENTORY DEPLETION (CHART 8)
    # --------------------------------------------------------------------------
    c7, c8 = st.columns(2)

    with c7:
        st.markdown("##### Chart 7 — Demand Sensing vs. Forecast Time Series")
        demand_hist = tools._demand_svc.get_demand_history(selected_sku, selected_depot, days=30)
        
        fig_ts = go.Figure()
        if not demand_hist.empty:
            dates = demand_hist["date"].tolist()
            observed = demand_hist["observed_sales"].tolist()
            corrected = demand_hist["corrected_demand"].tolist()
            daily_forecast = rec["forecast_demand"]

            # Shaded stockout censoring band
            stockout_days = demand_hist[demand_hist["is_stockout_flagged"]]
            for _, s_row in stockout_days.iterrows():
                fig_ts.add_vline(x=s_row["date"], line_width=1, line_dash="dash", line_color="#DC2626")

            # 1. Observed actual sales
            fig_ts.add_trace(go.Scatter(
                x=dates, y=observed, mode="lines+markers",
                name="Observed Actual Sales",
                line=dict(color=COLOR_TOKENS["OBSERVED_ACTUAL"], width=2),
                marker=dict(size=4),
            ))
            # 2. Corrected latent demand (censored demand)
            fig_ts.add_trace(go.Scatter(
                x=dates, y=corrected, mode="lines",
                name="Corrected Latent Demand (True Run-Rate)",
                line=dict(color=COLOR_TOKENS["CORRECTED_LATENT"], width=2.5, dash="dot"),
            ))
            # 3. Vintage Forecast line
            fig_ts.add_trace(go.Scatter(
                x=dates, y=[daily_forecast] * len(dates), mode="lines",
                name="Demand Sensing Forecast (Vintage W18)",
                line=dict(color=COLOR_TOKENS["VINTAGE_FORECAST"], width=2, dash="dash"),
            ))

        style_scm_figure(fig_ts, height=330, y_title="Daily Bottles")
        fig_ts.update_layout(title=f"Demand Sensing Series: {selected_sku} @ {selected_depot}")
        st.plotly_chart(fig_ts, use_container_width=True, config={"displayModeBar": False})
        st.caption("Red dashed vertical markers indicate stockout censoring events detected via QC dark-store logs.")

    with c8:
        st.markdown("##### Chart 8 — Projected Inventory Depletion & Cover Timeline")
        timeline_df = tools._inv_svc.project_inventory_depletion_timeline(
            selected_sku, selected_depot, daily_forecast_demand=rec["forecast_demand"], horizon_days=21
        )

        fig_dep = go.Figure()
        if not timeline_df.empty:
            t_dates = timeline_df["date"].tolist()
            closing = timeline_df["closing_stock"].tolist()
            target_stock = rec["target_stock"]

            # 21-day target stock line
            fig_dep.add_hline(y=target_stock, line_dash="dash", line_color=COLOR_TOKENS["HEALTHY_SURPLUS"], annotation_text="21d Target Stock")

            # Projected closing inventory sawtooth
            fig_dep.add_trace(go.Scatter(
                x=t_dates, y=closing, mode="lines+markers",
                name="Usable Projected Inventory",
                line=dict(color=COLOR_TOKENS["OBSERVED_ACTUAL"], width=2.5),
                fill="tozeroy",
                fillcolor="rgba(2, 132, 199, 0.08)",
            ))

            # Mark stock-out date if applicable
            proj_stockout = rec["projected_stockout_date"]
            if proj_stockout and "NONE" not in proj_stockout:
                fig_dep.add_vline(x=proj_stockout, line_width=2, line_dash="dash", line_color=COLOR_TOKENS["RISK_CRITICAL"], annotation_text="Projected Stock-Out")

        style_scm_figure(fig_dep, height=330, y_title="Available Bottles")
        fig_dep.update_layout(title="Forward 21-Day Depletion Trajectory with Dated Inbounds")
        st.plotly_chart(fig_dep, use_container_width=True, config={"displayModeBar": False})
        st.caption(f"Shelf-Life Status: {rec['shelf_life_status']} | MT/QC Gate: 60d | Near-Cliff Warning: 67d.")

    # --------------------------------------------------------------------------
    # ACTION TABLES & HUMAN APPROVAL
    # --------------------------------------------------------------------------
    st.markdown("<div style='margin-top:16px;'></div>", unsafe_allow_html=True)
    t_act, t_rep = st.tabs(["[FEASIBLE INTER-DEPOT REBALANCING PROPOSALS]", "[MANUAL STOCK-OUT REPORTING FORM]"])

    with t_act:
        proposals = tools.plan_rebalancing(sku_id=selected_sku)
        relevant_props = [p for p in proposals if p["destination_depot_id"] == selected_depot or p["origin_depot_id"] == selected_depot]

        if relevant_props:
            st.markdown(f"**{len(relevant_props)} Feasible Rebalancing Proposals Identified for {selected_sku} @ {selected_depot}:**")
            for prop in relevant_props:
                rec_id = prop["recommendation_id"]
                with st.container(border=True):
                    # Structured Exception Ticket Pattern
                    st.markdown(
                        f"**[{rec_id}] | [PRIORITY: {prop['priority']}] | [MODULE: {prop['module']}] | [STATUS: {prop['status']}]**"
                    )
                    st.markdown(f"**Diagnosis:** {prop['diagnosis']}")

                    # 4-Mini-Column Quantified Trade-Off Strip
                    tc1, tc2, tc3, tc4 = st.columns(4)
                    tc1.caption(f"**Action:** Transfer {prop['quantity_bottles']:,} btls from `{prop['origin_depot_id']}` to `{prop['destination_depot_id']}`")
                    tc2.caption(f"**Lead Time:** {prop['lead_time_days']}d transit + 1d approval = **{prop['eta_days']}d ETA**")
                    tc3.caption(f"**Cost Impact:** ₹{prop['cost_inr']:,.0f} vs **₹{prop['protected_contribution_inr']:,.0f}** Protected Contribution")
                    tc4.caption(f"**Shelf Life:** {prop['shelf_life_status']}")

                    # Inline 3-Button Action Controls
                    b_app, b_mod, b_rej = st.columns([1, 1, 2])
                    with b_app:
                        if st.button("Approve Execution", key=f"app_{rec_id}"):
                            res = approval.decide(rec_id, "APPROVE", approver_id="Depot-Planner-UI")
                            st.success(res.get("summary_message"))
                            st.rerun()
                    with b_mod:
                        mod_qty = st.number_input("Modify Qty", min_value=1000, max_value=50000, step=500, value=prop["quantity_bottles"], key=f"mod_qty_{rec_id}")
                        if st.button("Submit Modified", key=f"mod_btn_{rec_id}"):
                            res = approval.decide(rec_id, "MODIFY", approver_id="Depot-Planner-UI", modified_quantity_bottles=mod_qty)
                            st.info(res.get("summary_message"))
                            st.rerun()
                    with b_rej:
                        rej_note = st.text_input("Rejection Reason", placeholder="e.g. Donor local demand revised upwards", key=f"rej_note_{rec_id}")
                        if st.button("Reject with Note", key=f"rej_btn_{rec_id}"):
                            res = approval.decide(rec_id, "REJECT", approver_id="Depot-Planner-UI", notes=rej_note)
                            st.warning(res.get("summary_message"))
                            st.rerun()
        else:
            st.info(f"No active rebalancing transfers required for {selected_sku} at {selected_depot}. Inventory cover is healthy or donor stock is constrained.")

    with t_rep:
        st.markdown("##### Manual Stock-Out Incident Report")
        st.caption("Direct field reporting from dark stores, distributors, and Modern Trade partners.")

        with st.form("manual_stockout_form"):
            f_depot = st.selectbox("Depot", [d["depot_id"] for d in DEPOTS], index=depot_ids.index(selected_depot))
            f_sku = st.selectbox("SKU", list(SKUS.keys()), index=sku_ids.index(selected_sku))
            f_channel = st.selectbox("Impacted Channel", ["QC", "MT", "GT", "ALL"])
            f_unmet = st.number_input("Estimated Unmet Demand (Bottles)", min_value=100, max_value=200000, value=15000, step=500)
            f_reporter = st.text_input("Reported By", value="Dark-Store Ops Lead")
            f_source = st.text_input("Evidence / Source", value="Zepto/Blinkit Partner Stockout Portal")
            f_notes = st.text_area("Operational Notes", value="Zero inventory across 14 dark stores during peak weekend sales window.")
            submitted = st.form_submit_button("Submit Manual Stock-Out Report")

            if submitted:
                new_rep_id = f"REP-{datetime.datetime.now().strftime('%m%d%H%M')}"
                report_row = {
                    "report_id": new_rep_id,
                    "reported_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "depot_id": f_depot,
                    "sku_id": f_sku,
                    "channel": f_channel,
                    "reported_by": f_reporter,
                    "evidence_source": f_source,
                    "estimated_unmet_bottles": f_unmet,
                    "notes": f_notes,
                }
                append_csv_row("stockout_reports", report_row)
                st.success(f"Stockout Report [{new_rep_id}] successfully logged to stockout_reports.csv. Demand sensing engine updated.")
                st.rerun()
