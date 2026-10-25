"""Page 4 — AI Copilot & Exception Management for RIOT RADAR.

Provides:
- Active operating mode indicator (Live LLM API vs. Deterministic Fallback Engine)
- Autonomous LangGraph Detection Pipeline trigger
- Pending recommendation queue rendered as structured IBP Exception Tickets
- Human decision action controls (Approve, Modify, Reject) persisting directly to CSV
- Decision audit trail
"""

import os
import streamlit as st
import pandas as pd

import tools
import approval
from services.csv_store import load_csv


def render_ai_copilot():
    st.markdown("### [RIOT RADAR] AI Copilot & Exception Approval Queue")
    st.caption("Human-in-the-loop operational decision governance for Pulp Riot S&OP planners.")

    # --------------------------------------------------------------------------
    # OPERATING MODE & STATUS
    # --------------------------------------------------------------------------
    groq_key = os.getenv("GROQ_API_KEY")
    mode_label = "LIVE_LLM_API (Groq Llama 3 / Claude)" if groq_key else "DETERMINISTIC_FALLBACK_ENGINE (Safe Zero-Key SCM Rules)"
    badge_color = "#115E59" if groq_key else "#0F172A"
    badge_bg = "#CCFBF1" if groq_key else "#F1F5F9"

    m_col1, m_col2 = st.columns([3, 1])
    with m_col1:
        st.markdown(f"""
            <div style="background:{badge_bg}; border:1px solid #CBD5E1; border-radius:4px; padding:6px 12px; margin-bottom:12px;">
                <span style="font-size:0.75rem; font-weight:700; color:#475569; text-transform:uppercase;">Active Decision Engine:</span>
                <span style="font-size:0.80rem; font-weight:700; color:{badge_color}; margin-left:8px;">[{mode_label}]</span>
            </div>
        """, unsafe_allow_html=True)
    with m_col2:
        if st.button("Trigger Detection Pipeline", key="trigger_pipe_btn"):
            with st.spinner("Executing 6-Node LangGraph Detection Pipeline..."):
                res = tools.run_pipeline()
                st.success(f"Pipeline executed successfully. Generated {len(res.get('recommendations_generated', []))} new pending recommendations.")
                st.rerun()

    # --------------------------------------------------------------------------
    # PENDING RECOMMENDATIONS QUEUE
    # --------------------------------------------------------------------------
    pending_recs = approval.get_pending_recommendations()
    st.markdown(f"#### Active Pending Recommendation Tickets ({len(pending_recs)})")

    if not pending_recs.empty:
        for _, rec in pending_recs.iterrows():
            rec_id = rec["recommendation_id"]
            prio = rec["priority"]
            mod = rec["module"]
            status = rec["status"]
            prio_color = "#DC2626" if prio == "P1" else "#D97706"

            with st.container(border=True):
                # 1. Header Bar
                st.markdown(
                    f"<div style='background:#F8FAFC; padding:6px 10px; border-bottom:1px solid #E2E8F0; margin-bottom:8px;'>"
                    f"<b>[{rec_id}]</b> | "
                    f"<span style='color:{prio_color}; font-weight:700;'>[PRIORITY: {prio}]</span> | "
                    f"<b>[MODULE: {mod}]</b> | "
                    f"<i>[STATUS: {status}]</i>"
                    f"</div>",
                    unsafe_allow_html=True,
                )

                # 2. Bottleneck Diagnosis
                st.markdown(f"**Bottleneck Diagnosis:** {rec['diagnosis']}")

                # 3. Quantified Trade-off Strip (4 Mini-Columns)
                t1, t2, t3, t4 = st.columns(4)
                with t1:
                    st.caption(f"**Action:** {rec['action_type']}<br>Qty: **{int(float(rec['quantity_bottles'])):,} btls**<br>From: `{rec['origin_depot_id']}` -> `{rec['destination_depot_id']}`", unsafe_allow_html=True)
                with t2:
                    st.caption(f"**Lead Time:**<br>{rec['lead_time_days']}d Physical Transit<br>+ 1d Approval = **{rec['eta_days']}d ETA**", unsafe_allow_html=True)
                with t3:
                    cost = float(rec['cost_inr'])
                    benefit = float(rec['protected_contribution_inr'])
                    st.caption(f"**Financial Impact:**<br>Transfer Cost: ₹{cost:,.0f}<br>Protected Contrib: **₹{benefit:,.0f}**", unsafe_allow_html=True)
                with t4:
                    st.caption(f"**Shelf-Life Gate:**<br>{rec['shelf_life_status']}<br>Donor Post-Cover: **{rec['donor_post_cover_days']}d**", unsafe_allow_html=True)

                # 4. Action Controls (Inline 3-Button Bar)
                st.markdown("<div style='margin-top:6px;'></div>", unsafe_allow_html=True)
                b1, b2, b3 = st.columns([1.2, 1.2, 2.0])

                with b1:
                    if st.button("Approve Execution", key=f"copilot_app_{rec_id}"):
                        res = approval.decide(rec_id, "APPROVE", approver_id="Lead-Planner-Copilot")
                        st.success(res.get("summary_message"))
                        st.rerun()

                with b2:
                    mod_input = st.number_input(
                        "Modify Qty",
                        min_value=500, max_value=50000, step=500,
                        value=int(float(rec['quantity_bottles'])),
                        key=f"copilot_mod_{rec_id}",
                    )
                    if st.button("Submit Modified", key=f"copilot_btn_mod_{rec_id}"):
                        res = approval.decide(rec_id, "MODIFY", approver_id="Lead-Planner-Copilot", modified_quantity_bottles=mod_input)
                        st.info(res.get("summary_message"))
                        st.rerun()

                with b3:
                    reject_reason = st.text_input("Rejection Reason", placeholder="e.g. Alternate production run scheduled", key=f"copilot_note_{rec_id}")
                    if st.button("Reject with Note", key=f"copilot_btn_rej_{rec_id}"):
                        res = approval.decide(rec_id, "REJECT", approver_id="Lead-Planner-Copilot", notes=reject_reason)
                        st.warning(res.get("summary_message"))
                        st.rerun()
    else:
        st.info("No active recommendations awaiting human approval. All operational actions are up to date.")

    # --------------------------------------------------------------------------
    # AUDIT LOG TAB
    # --------------------------------------------------------------------------
    st.markdown("<div style='margin-top:16px;'></div>", unsafe_allow_html=True)
    with st.expander("[DECISION AUDIT LOG] Recorded Human Approvals & Pipeline State", expanded=False):
        approvals_df = load_csv("approvals")
        if not approvals_df.empty:
            st.dataframe(approvals_df, hide_index=True, use_container_width=True)
        else:
            st.caption("No human decisions logged yet.")

        st.markdown("**LangGraph Workflow State Persistence:**")
        wf_df = load_csv("workflow_state")
        if not wf_df.empty:
            st.dataframe(wf_df, hide_index=True, use_container_width=True)
        else:
            st.caption("No workflow state recorded.")
