---
name: demand-spike-triage
description: Use when scan_demand reports a SPIKE for any flavor, or the user asks whether a demand surge is real. Confirms the spike, checks for demand hidden by stock-outs, classifies it as transient or sustained, and hands off to rebalancing or escalation.
---
# Demand spike triage

1. Call `scan_demand`. For the flagged flavor note `multiplier_vs_baseline`, `first_flagged`, `sustained` and `confidence`.
2. Treat a spike seen on one channel only as medium confidence. Say so.
3. Call `forecast_demand` for the flavor. If `hidden_demand_pct` is above 10, state that stock-outs are masking demand and use the corrected `forecast_per_day`, not the raw sales figure.
4. Classify:
   - `sustained` true: plan for the new level (rebalancing, allocation, upstream check).
   - `sustained` false: recommend watching for 2-3 more days. Do not recommend production changes on a transient.
5. Call `find_surplus_and_shortage` and `plan_rebalancing` for that flavor. If any bottles remain in `residual_unfixable_units_14d`, load `network-gap-escalation`.
6. Call `rank_risks`, then brief the approver with `approval-briefing`. Always include the flag date next to the planner-notice date when it is known, so the detection delay is visible.

Never state a quantity, date or percentage that is not in a tool result.
