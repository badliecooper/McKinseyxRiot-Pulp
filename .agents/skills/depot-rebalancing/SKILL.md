---
name: depot-rebalancing
description: Use when some depots are short of a flavor while others hold surplus of it, or when asked how to move stock between depots. Tries free reallocation first, then feasible transfers, and checks each transfer against shelf life, donor cover and transit time.
---
# Depot rebalancing

Order of preference: reallocation (free) before transfers (Rs 1.50 per bottle, 2-4 days).

1. Call `find_surplus_and_shortage` for the flavor. If there are no shortage cells, stop and say so.
2. Call `recommend_allocation`. If the changes are large, recommend applying them at the next dispatch cycle (see `allocation-reset`) and treat transfers as the short-term bridge only.
3. Call `plan_rebalancing`. For every transfer read its `checks`:
   - `donor_keeps_target_cover` must be true, otherwise the transfer would create a new shortage at the origin.
   - `shelf_life_ok_all_channels` true means usable for MT and QC. If only `gt_only_shelf_life` is true, say the stock is usable for general trade only, because MT and QC reject stock under 60 days.
   - `arrives_before_stockout`. If false, report `units_lost_before_arrival` and say the transfer only shortens the stock-out.
4. Report cost (`cost_inr`) against protected contribution (`benefit_inr`). If cost is not clearly below benefit, say it is marginal.
5. Anything left in `residual_unfixable_units_14d` cannot be fixed by moving stock. Load `network-gap-escalation`.
6. A depot manager must confirm they can ship. Say this is a simulated confirmation, not proof of dispatch.
