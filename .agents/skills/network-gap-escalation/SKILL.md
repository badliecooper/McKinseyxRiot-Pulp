---
name: network-gap-escalation
description: Use when plan_rebalancing leaves a residual shortage that no depot transfer can cover, or when a flavor is short across the whole network. Lays out upstream options in order of cost, with the constraints that apply.
---
# Network-gap escalation

1. Call `check_upstream_supply` for the flavor. Read `residual_gap_per_month`.
2. Present options in this order, cheapest first:
   - Production mix shift from over-supplied flavors: `mix_shift_available_per_month`, no extra cost per bottle. Check `gap_covered_with_mix_shift`.
   - In-house headroom: `inhouse_headroom_per_month` (plants ran at 95% utilisation, so this is small).
   - Co-packer: capped at `copacker_cap_per_month`, 14-day notice, extra cost `copacker_extra_cost_per_bottle`. Report `copacker_net_contribution_per_bottle` so the approver sees it is still positive.
3. Show timing: co-packer volume lands about 14 days after the order. Compare with the days to stock-out.
4. Add the pulp context from `pulp_notes`. Passionfruit has one cooperative, one road and about 14 days of cover. Dragonfruit lead time is 6-8 weeks, so ordering now cannot fix a 14-day gap.
5. Never recommend more volume than headroom plus co-packer cap plus mix shift. If the gap is larger, say the remainder is unmet demand and the human must choose which channels to protect.
6. Supply is a high-level check in this MVP. Say that the production planner confirms feasibility.
