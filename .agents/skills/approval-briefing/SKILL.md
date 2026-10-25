---
name: approval-briefing
description: Use whenever the agent presents a recommendation for a human to approve, reject or edit. Gives a fixed briefing format built only from tool outputs.
---
# Approval briefing

Format every recommendation like this:

- **Observation:** what happened and when it was detected.
- **Diagnosis:** the cause, tracing across modules (demand shift -> allocation -> shortage; shortage -> hidden demand).
- **If no action:** projected impact in Rs (`impact_if_no_action_inr`), in crore.
- **Recommended action:** exactly what the tool returned, with quantities.
- **Cost and benefit:** `est_cost_inr` against `est_benefit_inr`.
- **Trade-off:** from the risk's `tradeoffs`, plus any failed or marginal check.
- **Confidence:** from the tool, with the reason.
- **Approver and decision needed:** who decides, and the options (approve, edit, reject).

Rules:
1. Only queue a recommendation with `submit_for_approval(risk_id)` using an id from `rank_risks`. The agent cannot approve and cannot invent a recommendation.
2. Say "awaiting approval". Never say it has been executed or shipped.
3. Keep it under ten lines unless the user asks for detail.
