"""Page 1 — Control Tower for RIOT RADAR.

Displays:
- Five-module health ribbon (Demand, Supply, Inventory, Distribution, Transportation)
- Exactly six national KPI cards
- Active Alarms & Exceptions feed
- Chart 1: Flavour × Depot Heatmap
- Chart 2: Demand vs. Inventory Risk Matrix
- Chart 3: Depot Rebalancing Network
- Chart 4: Historical Loss Attribution & Interactive Root-Cause Sliders
- Exactly three bottom expanders with Chart 5 (WAPE Grouped Bar) and Chart 6 (Bias Over Time)
"""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np

import tools
from config.business_rules import (
    COLOR_TOKENS,
    SKUS,
    DEPOTS,
    HISTORICAL_STOCKOUT_LOST_REVENUE_INR_CR,
    HISTORICAL_FOREGONE_CONTRIBUTION_INR_CR,
    HISTORICAL_WRITEOFFS_DISCOUNTS_INR_CR,
    HISTORICAL_AIR_FREIGHT_INR_CR,
    HISTORICAL_BOTTOM_LINE_EXPOSURE_INR_CR,
    YEAR_1_SYSTEM_BUDGET_CAP_INR_CR,
    BREAK_EVEN_RECOVERY_HURDLE_PCT,
    ROOT_CAUSE_CONFIG,
)
from services.loss_attribution import redistribute_root_causes, calculate_root_cause_exposures
from ui.components.theme import style_scm_figure


def render_control_tower():
    st.markdown("### [RIOT RADAR] Enterprise Supply Chain Control Tower")
    st.caption("Pulp Riot Juice Co. — Operational Exception Management & Demand Sensing")

    # --------------------------------------------------------------------------
    # A. FIVE-MODULE HEALTH RIBBON
    # --------------------------------------------------------------------------
    ribbon = tools.get_health_ribbon()
    cols = st.columns(5)
    for idx, (mod_name, data) in enumerate(ribbon.items()):
        status = data["status"]
        css_class = "rag-critical" if status == "CRITICAL" else ("rag-warn" if status == "WARN" else "rag-ok")
        with cols[idx]:
            st.markdown(f"""
                <div style="background:#FFFFFF; border:1px solid #E2E8F0; border-radius:4px; padding:8px 10px; min-height:85px;">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
                        <span style="font-size:0.75rem; font-weight:700; color:#334155; text-transform:uppercase;">{mod_name}</span>
                        <span class="rag-badge {css_class}">[{status}]</span>
                    </div>
                    <div style="font-size:0.75rem; color:#0F172A; font-weight:600; line-height:1.2;">{data['reason']}</div>
                    <div style="font-size:0.70rem; color:#64748B; margin-top:4px;">{data['signal']}</div>
                </div>
            """, unsafe_allow_html=True)

    st.markdown("<div style='margin-top:12px;'></div>", unsafe_allow_html=True)

    # --------------------------------------------------------------------------
    # B. EXACTLY SIX NATIONAL KPI CARDS
    # --------------------------------------------------------------------------
    kpis = tools.get_national_kpis()
    kcol1, kcol2, kcol3, kcol4, kcol5, kcol6 = st.columns(6)

    kcol1.metric("Depots at Risk", kpis["depots_at_risk"], help="Depots holding SKU cover <7d or 60-67d near-cliff stock")
    kcol2.metric("Forecast WAPE", kpis["forecast_wape_pct"], delta=f"-19.3% vs Naive {kpis['naive_benchmark_wape_pct']}", delta_color="inverse")
    kcol3.metric("Projected Shortage", f"{kpis['projected_shortage_bottles']:,} btls", help="Unmet corrected demand over next 21 days")
    kcol4.metric("Transfer Opportunities", f"{kpis['transfer_opportunities_count']} Lanes", help="Feasible non-duplicate inter-depot transfers")
    kcol5.metric("Detection Lead Time", f"+{kpis['detection_lead_time_days']} Days", help="Earlier detection advantage vs monthly S&OP spreadsheets")
    kcol6.metric("Pending Decisions", f"{kpis['pending_decisions_count']} Actions", help="Operational recommendations requiring human approval")

    st.markdown("<div style='margin-top:14px;'></div>", unsafe_allow_html=True)

    # --------------------------------------------------------------------------
    # ALARM & EXCEPTION MANAGEMENT SYSTEM FEED
    # --------------------------------------------------------------------------
    with st.expander("[ACTIVE ALARMS & EXCEPTION FEED] Real-Time Supply Chain Breaches", expanded=True):
        alarms_df = tools._risk_svc.load_csv("alarms") if hasattr(tools, "_risk_svc") else pd.DataFrame()
        if not alarms_df.empty:
            f1, f2, f3 = st.columns(3)
            with f1:
                sel_sev = st.multiselect("Filter Severity", options=["CRITICAL", "WARNING", "INFO"], default=["CRITICAL", "WARNING"])
            with f2:
                sel_status = st.multiselect("Filter Status", options=["NEW", "ACKNOWLEDGED", "RESOLVED"], default=["NEW", "ACKNOWLEDGED"])
            with f3:
                depot_list = ["ALL"] + [d["depot_id"] for d in DEPOTS]
                sel_depot = st.selectbox("Filter Depot", depot_list)

            filtered_alarms = alarms_df.copy()
            if sel_sev:
                filtered_alarms = filtered_alarms[filtered_alarms["severity"].isin(sel_sev)]
            if sel_status:
                filtered_alarms = filtered_alarms[filtered_alarms["status"].isin(sel_status)]
            if sel_depot != "ALL":
                filtered_alarms = filtered_alarms[filtered_alarms["depot_id"] == sel_depot]

            st.caption(f"Showing {len(filtered_alarms)} active exception alarms:")
            for _, alarm in filtered_alarms.iterrows():
                a_id = alarm["alarm_id"]
                sev = alarm["severity"]
                status = alarm["status"]
                sev_color = "#DC2626" if sev == "CRITICAL" else "#D97706"
                
                with st.container(border=True):
                    c_hdr, c_act = st.columns([4, 1])
                    with c_hdr:
                        st.markdown(
                            f"<span style='color:{sev_color}; font-weight:700;'>[{sev}]</span> "
                            f"<b>{alarm['title']}</b> | <code>{alarm.get('sku_id','')} @ {alarm.get('depot_id','')}</code> | "
                            f"<i>Status: {status}</i>",
                            unsafe_allow_html=True,
                        )
                        st.markdown(f"<span style='font-size:0.80rem; color:#334155;'><b>Diagnosis:</b> {alarm['description']} (Observed: {alarm['observed_value']} vs Threshold: {alarm['threshold_value']})</span>", unsafe_allow_html=True)
                        st.markdown(f"<span style='font-size:0.80rem; color:#0F172A;'><b>Prescribed Action:</b> {alarm['recommended_action']}</span>", unsafe_allow_html=True)
                    with c_act:
                        if status == "NEW":
                            if st.button("Acknowledge", key=f"ack_{a_id}"):
                                tools._risk_svc.acknowledge_alarm(a_id)
                                st.rerun()
                        elif status == "ACKNOWLEDGED":
                            if st.button("Resolve", key=f"res_{a_id}"):
                                tools._risk_svc.resolve_alarm(a_id)
                                st.rerun()
                        else:
                            st.caption("[RESOLVED]")
        else:
            st.info("No active alarms recorded.")

    # --------------------------------------------------------------------------
    # CHARTS ROW 1: HEATMAP & RISK MATRIX
    # --------------------------------------------------------------------------
    st.markdown("<div style='margin-top:14px;'></div>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)

    with c1:
        st.markdown("##### Chart 1 — Flavour × Depot Heatmap")
        metric_choice = st.selectbox(
            "Heatmap Operational Metric",
            ["Allocation Gap (Bottles)", "Days of Cover (DoC)", "Forecast Error (WAPE %)"],
            key="hm_metric",
        )
        grid_df = tools.get_sku_depot_grid()
        
        if metric_choice == "Allocation Gap (Bottles)":
            z_col = "allocation_gap"
            color_scale = "Reds"
            z_title = "Deficit (Btls)"
        elif metric_choice == "Days of Cover (DoC)":
            z_col = "days_of_cover"
            color_scale = "Tealrose"
            z_title = "Days"
        else:
            z_col = "wape_pct"
            color_scale = "Viridis"
            z_title = "WAPE %"

        pivot = grid_df.pivot(index="depot_id", columns="sku_id", values=z_col).fillna(0)
        fig_hm = go.Figure(data=go.Heatmap(
            z=pivot.values,
            x=list(pivot.columns),
            y=list(pivot.index),
            colorscale=color_scale,
            colorbar=dict(title=z_title),
        ))
        fig_hm.update_layout(title="45 SKU–Depot Operational Grid Matrix")
        style_scm_figure(fig_hm, height=330)
        st.plotly_chart(fig_hm, use_container_width=True, config={"displayModeBar": False})
        st.caption("Note: Synthetic demonstration data calibrated to 9 regional depots and 5 finished goods SKUs.")

    with c2:
        st.markdown("##### Chart 2 — Demand vs. Inventory Risk Matrix")
        fig_scatter = go.Figure()

        # Add priority risk quadrant rectangle (High Demand > 4000 btls/d, Low Cover < 7 days)
        fig_scatter.add_vrect(
            x0=3500, x1=grid_df["forecast_demand"].max() * 1.1,
            y0=0, y1=7,
            fillcolor="#FEE2E2", opacity=0.3, line_width=1, line_dash="dash", line_color="#DC2626",
            annotation_text="High Demand / Low Cover Risk Zone", annotation_position="top right"
        )
        # Add 21d Target Cover line
        fig_scatter.add_hline(y=21, line_dash="dash", line_color=COLOR_TOKENS["HEALTHY_SURPLUS"], annotation_text="21d Target Cover")

        # Scatter points
        fig_scatter.add_trace(go.Scatter(
            x=grid_df["forecast_demand"],
            y=grid_df["days_of_cover"],
            mode="markers+text",
            text=grid_df["sku_id"],
            textposition="top center",
            marker=dict(
                size=11,
                color=np.where(grid_df["days_of_cover"] < 7, COLOR_TOKENS["RISK_CRITICAL"],
                     np.where(grid_df["days_of_cover"] < 14, COLOR_TOKENS["RISK_WARNING"], COLOR_TOKENS["HEALTHY_SURPLUS"])),
                line=dict(width=1, color="#0F172A"),
            ),
            hovertext=[
                f"<b>{r['sku_id']} @ {r['depot_id']}</b><br>Flavour: {r['flavour']}<br>Demand: {r['forecast_demand']:,} btls/d<br>Cover: {r['days_of_cover']} days<br>Gap: {r['allocation_gap']:,} btls<br>Stockout: {r['projected_stockout_date']}"
                for _, r in grid_df.iterrows()
            ],
            hoverinfo="text",
        ))
        style_scm_figure(fig_scatter, height=330, y_title="Days of Cover (DoC)")
        fig_scatter.update_layout(xaxis_title="Corrected Daily Forecast Demand (Bottles/Day)")
        st.plotly_chart(fig_scatter, use_container_width=True, config={"displayModeBar": False})
        st.caption("Thresholds: Red (<7d Critical), Amber (7-14d Warning), Teal (>=21d Target).")

    # --------------------------------------------------------------------------
    # CHARTS ROW 2: REBALANCING NETWORK & LOSS ATTRIBUTION
    # --------------------------------------------------------------------------
    st.markdown("<div style='margin-top:14px;'></div>", unsafe_allow_html=True)
    c3, c4 = st.columns(2)

    with c3:
        st.markdown("##### Chart 3 — Depot Rebalancing Network")
        proposals = tools.plan_rebalancing()
        
        # Display Rebalancing Proposals Summary
        if proposals:
            fig_net = go.Figure()
            # Plot proposals as connected directed edges
            origins = [p["origin_depot_id"] for p in proposals]
            dests = [p["destination_depot_id"] for p in proposals]
            skus_prop = [p["sku_id"] for p in proposals]
            qtys = [p["quantity_bottles"] for p in proposals]
            costs = [p["cost_inr"] for p in proposals]

            # Simplified bar representation of feasible transfer opportunities
            fig_net.add_trace(go.Bar(
                x=[f"{p['sku_id']}: {p['origin_depot_id']} -> {p['destination_depot_id']}" for p in proposals[:6]],
                y=[p["quantity_bottles"] for p in proposals[:6]],
                marker_color=COLOR_TOKENS["HEALTHY_SURPLUS"],
                text=[f"₹{p['cost_inr']:,.0f} | ETA: {p['eta_days']}d" for p in proposals[:6]],
                textposition="auto",
            ))
            style_scm_figure(fig_net, height=330, y_title="Transfer Quantity (Bottles)")
            fig_net.update_layout(title="Top Feasible Inter-Depot Transfers (Donor Safe Cover >= 21d)")
            st.plotly_chart(fig_net, use_container_width=True, config={"displayModeBar": False})
            st.caption("Feasibility Guardrails: Enforces donor >=21d post-cover and 67d shelf-life MT/QC rejection boundary.")
        else:
            st.info("No inter-depot transfers currently required; network cover is balanced.")

    with c4:
        st.markdown("##### Chart 4 — Historical Loss Attribution (Non-Overlapping)")
        loss = tools.get_loss_attribution()

        fig_loss = go.Figure(data=[
            go.Bar(
                name="Top-Line Gross",
                x=["Stock-Out Lost Revenue"],
                y=[loss["stockout_lost_revenue_inr_cr"]],
                marker_color="#334155",
                text=[f"₹{loss['stockout_lost_revenue_inr_cr']} Cr"],
                textposition="auto",
            ),
            go.Bar(
                name="Bottom-Line Exposure Components",
                x=["Foregone Contribution", "Write-offs & Discounts", "Emergency Air Freight"],
                y=[loss["foregone_contribution_inr_cr"], loss["writeoffs_and_discounts_inr_cr"], loss["emergency_air_freight_inr_cr"]],
                marker_color=["#7C3AED", "#D97706", "#DC2626"],
                text=[f"₹{loss['foregone_contribution_inr_cr']} Cr", f"₹{loss['writeoffs_and_discounts_inr_cr']} Cr", f"₹{loss['emergency_air_freight_inr_cr']} Cr"],
                textposition="auto",
            ),
        ])
        style_scm_figure(fig_loss, height=270, y_title="₹ Crore")
        fig_loss.update_layout(barmode="group", title="Historical Loss Categories (Separated, Non-Overlapping)")
        st.plotly_chart(fig_loss, use_container_width=True, config={"displayModeBar": False})

        # Interactive Root-Cause Attribution Model for ₹46.08 Cr
        st.markdown("###### Interactive Root-Cause Attribution of ₹46.08 Cr Stock-Out Loss")
        st.caption("Adjust sliders to model root-cause sensitivity. Redundant shares redistribute deterministically to sum to 100%.")

        if "rc_shares" not in st.session_state:
            st.session_state["rc_shares"] = {
                "late_demand_detection": ROOT_CAUSE_CONFIG["late_demand_detection"]["default_pct"],
                "stale_allocation_censored_loop": ROOT_CAUSE_CONFIG["stale_allocation_censored_loop"]["default_pct"],
                "single_source_pulp_rationing": ROOT_CAUSE_CONFIG["single_source_pulp_rationing"]["default_pct"],
            }

        sc1, sc2, sc3 = st.columns(3)
        with sc1:
            val1 = st.slider(
                "Late Demand Detection (30-40%)",
                min_value=30.0, max_value=40.0,
                value=st.session_state["rc_shares"]["late_demand_detection"],
                step=1.0, key="slider_late",
            )
            if val1 != st.session_state["rc_shares"]["late_demand_detection"]:
                st.session_state["rc_shares"], _, _ = redistribute_root_causes("late_demand_detection", val1, st.session_state["rc_shares"])
                st.rerun()

        with sc2:
            val2 = st.slider(
                "Stale Allocation Loop (35-45%)",
                min_value=35.0, max_value=45.0,
                value=st.session_state["rc_shares"]["stale_allocation_censored_loop"],
                step=1.0, key="slider_stale",
            )
            if val2 != st.session_state["rc_shares"]["stale_allocation_censored_loop"]:
                st.session_state["rc_shares"], _, _ = redistribute_root_causes("stale_allocation_censored_loop", val2, st.session_state["rc_shares"])
                st.rerun()

        with sc3:
            val3 = st.slider(
                "Pulp Disruption (20-30%)",
                min_value=20.0, max_value=30.0,
                value=st.session_state["rc_shares"]["single_source_pulp_rationing"],
                step=1.0, key="slider_pulp",
            )
            if val3 != st.session_state["rc_shares"]["single_source_pulp_rationing"]:
                st.session_state["rc_shares"], _, _ = redistribute_root_causes("single_source_pulp_rationing", val3, st.session_state["rc_shares"])
                st.rerun()

        res_attr = calculate_root_cause_exposures(st.session_state["rc_shares"])
        b1, b2, b3 = st.columns(3)
        b1.caption(f"Late Detection: **₹{res_attr['breakdown']['late_demand_detection']['allocated_revenue_exposure_inr_cr']} Cr** (Contrib: ₹{res_attr['breakdown']['late_demand_detection']['allocated_contribution_exposure_inr_cr']} Cr)")
        b2.caption(f"Stale Allocation: **₹{res_attr['breakdown']['stale_allocation_censored_loop']['allocated_revenue_exposure_inr_cr']} Cr** (Contrib: ₹{res_attr['breakdown']['stale_allocation_censored_loop']['allocated_contribution_exposure_inr_cr']} Cr)")
        b3.caption(f"Pulp Disruption: **₹{res_attr['breakdown']['single_source_pulp_rationing']['allocated_revenue_exposure_inr_cr']} Cr** (Contrib: ₹{res_attr['breakdown']['single_source_pulp_rationing']['allocated_contribution_exposure_inr_cr']} Cr)")
        st.markdown(f"<div class='synthetic-badge'>{res_attr['disclaimer']}</div>", unsafe_allow_html=True)

    # --------------------------------------------------------------------------
    # G. EXACTLY THREE BOTTOM EXPANDERS
    # --------------------------------------------------------------------------
    st.markdown("<div style='margin-top:16px;'></div>", unsafe_allow_html=True)

    with st.expander("[EXPANDER 1] Bidirectional Causal Loop: Demand ↔ Distribution Architecture", expanded=False):
        st.markdown("""
        **Operational Mechanism of the Censored-Demand Blind Spot:**
        1. **Signal Ingestion:** Quick Commerce (QC) daily dark-store sell-through surges 4.1x, but traditional spreadsheet planners receive monthly consolidated distributor dispatches with 30-day latency.
        2. **Censored Demand Loop:** Depots run dry within 4 days. Unmet demand generates no invoices, creating a false appearance of 'flat sales'.
        3. **Stale Allocation Loop:** Next month's production allocation uses historical unadjusted sales, perpetuating chronic under-allocation to high-velocity depots while over-allocating to stagnant depots.
        4. **RIOT RADAR Closed-Loop Interventions:**
           `Signal -> Detect -> Diagnose -> Forecast Sensing -> Inter-Depot Rebalancing -> Recommend -> Human Approval -> Audit Log`.
        """)

    with st.expander("[EXPANDER 2] Feasibility, 15-Planner Adoption, Break-Even ROI & ₹2.5 Cr Budget Guardrail", expanded=False):
        st.markdown(f"""
        **Financial Discipline & Institutional Feasibility:**
        - **Total Bottom-Line Exposure:** ₹14.75 Cr (Foregone Contribution) + ₹6.00 Cr (Write-offs) + ₹3.20 Cr (Air Freight) = **₹23.95 Cr Bottom-Line Exposure**.
        - **Year-1 Rollout Budget Cap:** **₹2.50 Cr** system cap represents an illustrative **10.4% Break-Even Recovery Hurdle**.
        - **Planner Change Management:** Designed for the existing team of 15 spreadsheet planners. Deterministic calculation engines provide complete mathematical transparency without black-box hallucination.
        - **Human-in-the-Loop Safeguard:** The AI Copilot proposes actions; every physical transfer or pulp rationing decision requires explicit human authorization.
        """)

    with st.expander("[EXPANDER 3] Weekly Supply Chain Intelligence Report Preview & Accuracy Evaluation", expanded=True):
        st.markdown("##### Forecast Accuracy Benchmark & Bias Over Time")
        pcol1, pcol2 = st.columns(2)

        with pcol1:
            st.markdown("###### Chart 5 — Forecast Accuracy Grouped Bar Chart")
            # Grouped bar comparing RIOT RADAR vs Naive benchmark across 3 targets
            fig_acc = go.Figure(data=[
                go.Bar(
                    name="RIOT RADAR Sensing",
                    x=["Observed Sales", "Corrected Latent Demand", "Synthetic Ground Truth"],
                    y=[16.5, 10.7, 9.4],
                    marker_color=COLOR_TOKENS["VINTAGE_FORECAST"],
                    text=["16.5%", "10.7%", "9.4%"],
                    textposition="auto",
                ),
                go.Bar(
                    name="Naive Last-Week Benchmark",
                    x=["Observed Sales", "Corrected Latent Demand", "Synthetic Ground Truth"],
                    y=[24.8, 22.4, 25.1],
                    marker_color=COLOR_TOKENS["NEUTRAL_BASELINE"],
                    text=["24.8%", "22.4%", "25.1%"],
                    textposition="auto",
                ),
            ])
            style_scm_figure(fig_acc, height=270, y_title="WAPE % (Lower is Better)")
            fig_acc.update_layout(barmode="group", title="Forecast WAPE Benchmark (Vintage W18)")
            st.plotly_chart(fig_acc, use_container_width=True, config={"displayModeBar": False})
            st.caption("Evaluated on identical 7-day forward window. Synthetic ground truth is a demo construct.")

        with pcol2:
            st.markdown("###### Chart 6 — Forecast Error & Bias Over Time")
            # Tracking WAPE and Bias across weeks
            weeks = ["W14", "W15", "W16", "W17", "W18"]
            wape_trend = [28.5, 26.1, 21.4, 15.2, 10.7]
            bias_trend = [-14.2, -11.0, -6.5, +2.1, -1.8]

            fig_bias = go.Figure()
            fig_bias.add_trace(go.Scatter(
                x=weeks, y=wape_trend, mode="lines+markers",
                name="WAPE %", line=dict(color=COLOR_TOKENS["VINTAGE_FORECAST"], width=2)
            ))
            fig_bias.add_trace(go.Scatter(
                x=weeks, y=bias_trend, mode="lines+markers",
                name="Forecast Bias %", line=dict(color=COLOR_TOKENS["CORRECTED_LATENT"], width=2, dash="dot")
            ))
            fig_bias.add_hline(y=0, line_dash="solid", line_color="#94A3B8")
            style_scm_figure(fig_bias, height=270, y_title="Percentage (%)")
            fig_bias.update_layout(title="Forecast Error Convergence & Bias Reduction")
            st.plotly_chart(fig_bias, use_container_width=True, config={"displayModeBar": False})
            st.caption("Negative Bias = Underforecasting; Positive Bias = Overforecasting.")
