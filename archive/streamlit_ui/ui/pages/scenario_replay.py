"""Page 3 — Scenario Replay for RIOT RADAR.

Compares:
- Historical Baseline: monthly mix, delayed detection (14-21d), ad-hoc rationing, and stock-outs.
- RIOT RADAR: early signal sensing, corrected demand, feasible rebalancing, and deterministic recipe rationing.

Displays:
- Four scenario KPIs (Detection Advantage, Shortage Reduction, Rebalancing Coverage %, Net Mitigation Cost)
- Chart 9: Intervention Impact Waterfall
- Chart 10: Scenario Timeline & Cover Comparison (PR-DP Viral Spike vs May Highway Disruption)
"""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np

import tools
from config.business_rules import COLOR_TOKENS
from ui.components.theme import style_scm_figure


def render_scenario_replay():
    st.markdown("### [RIOT RADAR] Scenario Replay — Historical Baseline vs. Sensing Control Tower")
    st.caption("Quantitative comparison of early detection advantages and deterministic supply interventions.")

    # Scenario selection
    scenario_choice = st.radio(
        "Select Supply Chain Disruption Scenario",
        [
            "Scenario A: Dragon Passion (PR-DP) Fourfold QC Viral Surge (May 2026)",
            "Scenario B: Northeast Passionfruit Highway Closure — 3-Week Road Blockade (May 2026)",
        ],
        horizontal=True,
    )

    scenario_key = "PR_DP_VIRAL_SPIKE" if "Scenario A" in scenario_choice else "PASSIONFRUIT_HIGHWAY_CLOSURE"
    timeline_data = tools._scenario_svc.get_scenario_timeline_comparison(scenario_key)

    # --------------------------------------------------------------------------
    # FOUR SCENARIO KPIS
    # --------------------------------------------------------------------------
    st.markdown("<div style='margin-top:10px;'></div>", unsafe_allow_html=True)
    k1, k2, k3, k4 = st.columns(4)

    k1.metric(
        "Detection Advantage",
        f"+{timeline_data['detection_advantage_days']} Days",
        delta="Early Warning vs Spreadsheets",
        help="Planner-notice date minus RIOT RADAR agent flag date",
    )
    k2.metric(
        "Shortage Reduction",
        f"{timeline_data['stockout_prevented_bottles']:,} btls",
        help="Direct bottles protected from stock-out via feasible transfers & rationing",
    )
    k3.metric(
        "Rebalancing Coverage %",
        "76.4%",
        help="Feasible transfer-covered shortage divided by total projected shortage",
    )
    mit_cost = 117000 if scenario_key == "PR_DP_VIRAL_SPIKE" else 32000000  # ₹1.17 Lakh transfer vs ₹3.20 Cr air freight
    k4.metric(
        "Net Mitigation Cost",
        f"₹{mit_cost/100000:.2f} L" if mit_cost < 10000000 else f"₹{mit_cost/10000000:.2f} Cr",
        help="Transfer costs (@ ₹1.50/btl) or emergency air freight trigger",
    )

    st.markdown("<div style='margin-top:14px;'></div>", unsafe_allow_html=True)

    # --------------------------------------------------------------------------
    # CHARTS: WATERFALL (CHART 9) & TIMELINE (CHART 10)
    # --------------------------------------------------------------------------
    c9, c10 = st.columns(2)

    with c9:
        st.markdown("##### Chart 9 — Intervention Impact Waterfall")
        # Waterfall breakdown
        if scenario_key == "PR_DP_VIRAL_SPIKE":
            x_steps = ["Baseline Projected Shortage", "Inter-Depot Transfers", "Plant Overtime Rescheduling", "Residual Unmet Demand"]
            y_steps = [102000, -58000, -20000, 24000]
            measure_types = ["absolute", "relative", "relative", "total"]
            text_labels = ["102,000 btls", "-58,000 btls (@ ₹1.50)", "-20,000 btls", "24,000 btls"]
        else:
            x_steps = ["Baseline Pulp Shortage", "Deterministic Rationing (Protect PR-DP)", "Emergency Air Freight Contingency", "Residual Deficit"]
            y_steps = [125000, -45000, -60000, 20000]
            measure_types = ["absolute", "relative", "relative", "total"]
            text_labels = ["125,000 btls eq", "-45,000 btls (PR-PP -35%)", "-60,000 btls (₹3.20 Cr)", "20,000 btls eq"]

        fig_waterfall = go.Figure(go.Waterfall(
            name="Intervention Impact",
            orientation="v",
            measure=measure_types,
            x=x_steps,
            y=y_steps,
            text=text_labels,
            textposition="outside",
            connector=dict(line=dict(color="#CBD5E1")),
            decreasing=dict(marker=dict(color=COLOR_TOKENS["HEALTHY_SURPLUS"])),
            increasing=dict(marker=dict(color=COLOR_TOKENS["RISK_CRITICAL"])),
            totals=dict(marker=dict(color=COLOR_TOKENS["OBSERVED_ACTUAL"])),
        ))
        style_scm_figure(fig_waterfall, height=340, y_title="Finished Bottles / Pulp Equivalent")
        fig_waterfall.update_layout(title="Shortage Mitigation Waterfall (Feasible Levers Only)")
        st.plotly_chart(fig_waterfall, use_container_width=True, config={"displayModeBar": False})
        st.caption("SCM Guardrail: Co-packer provides bottling line capacity (+25% cost) but CANNOT resolve raw pulp scarcity.")

    with c10:
        st.markdown("##### Chart 10 — Scenario Timeline & Cover Trajectory Comparison")
        # Comparison of inventory cover trajectory: Historical vs RIOT RADAR
        days = list(range(1, 22))
        if scenario_key == "PR_DP_VIRAL_SPIKE":
            # Historical crashed to 0 at day 5 and stayed zero for 12 days
            historical_cover = [12, 9, 6, 3, 0.5, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 4, 8, 12, 15]
            # RIOT RADAR detected at day 2, approved day 3, transfer arrived day 6, kept cover >= 7d
            radar_cover = [12, 10, 8, 7.5, 7.0, 14.5, 13.8, 13.0, 12.2, 18.0, 17.2, 16.5, 16.0, 15.2, 18.0, 17.5, 17.0, 16.5, 16.0, 15.5, 15.0]
        else:
            historical_cover = [14, 13, 12, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1, 0, 0, 0, 0, 0, 0, 0]
            radar_cover = [14, 13.5, 13, 12.5, 12, 11.5, 11, 10.5, 10, 9.5, 9.0, 15.5, 15.0, 14.5, 14.0, 13.5, 13.0, 12.5, 12.0, 11.5, 11.0]

        fig_timeline = go.Figure()
        fig_timeline.add_trace(go.Scatter(
            x=days, y=historical_cover, mode="lines+markers",
            name="Historical Baseline (Delayed Month-End Notice)",
            line=dict(color=COLOR_TOKENS["RISK_CRITICAL"], width=2.5, dash="dash"),
        ))
        fig_timeline.add_trace(go.Scatter(
            x=days, y=radar_cover, mode="lines+markers",
            name="RIOT RADAR (Early Sensing & Rebalancing)",
            line=dict(color=COLOR_TOKENS["HEALTHY_SURPLUS"], width=2.5),
        ))
        fig_timeline.add_hline(y=7, line_dash="dash", line_color="#DC2626", annotation_text="Critical Stock-Out Boundary (7d)")
        fig_timeline.add_hline(y=21, line_dash="dash", line_color="#0D9488", annotation_text="21d Target Cover")

        style_scm_figure(fig_timeline, height=340, y_title="Days of Cover (DoC)")
        fig_timeline.update_layout(title="Inventory Cover Trajectory (Historical vs Control Tower)")
        st.plotly_chart(fig_timeline, use_container_width=True, config={"displayModeBar": False})
        st.caption(f"Signal Date: {timeline_data['first_qc_signal_date']} | Agent Flag: {timeline_data['agent_flag_date']} | Historical Notice: {timeline_data['historical_planner_notice_date']}.")

    # Strategic supply check note
    st.markdown("<div style='margin-top:14px;'></div>", unsafe_allow_html=True)
    with st.container(border=True):
        st.markdown("**Strategic Supply Constraints & Raw Material Economics:**")
        p1, p2, p3 = st.columns(3)
        p1.markdown("- **Bottling Line Capacity:** 2 plants @ 2.5 Cr btls/mo (operating at 95% utilization).")
        p2.markdown("- **Passionfruit Pulp Recipe Priority:** PR-DP yields **₹548.57 / kg pulp** vs PR-PP **₹274.29 / kg pulp** (2.0x higher contribution efficiency).")
        p3.markdown("- **Dragonfruit Import Constraint:** PR-DB uses 40% imported pulp on **6-8 week quarterly lead time** requiring rigid advance booking.")
