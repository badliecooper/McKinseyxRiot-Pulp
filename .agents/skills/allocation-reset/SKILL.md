---
name: allocation-reset
description: Use when allocation to depots has drifted away from forecast demand, when a new or fast-changing flavor is short at some depots, or when asked for the root cause of stock ending up in the wrong places. Re-slices the same total supply across depots by forecast share.
---
# Allocation reset (root-cause fix)

Root cause in the case: depot allocations are reset monthly from last year's flavor mix, so a new or fast-moving flavor is under-allocated and slow flavors pile up.

1. Call `recommend_allocation` (all flavors, or the one in question).
2. Report the largest changes: depot, flavor, `current_inbound_per_day`, `recommended_per_day`, `change_pct`.
3. State clearly: this moves existing supply between depots. It adds no bottles, so it cannot fix a network-wide shortage. Cost is zero freight.
4. Recommend applying it at the next dispatch cycle, and moving to a weekly review while demand is shifting.
5. Pair it with `depot-rebalancing` for stock already sitting in the wrong depot.
6. If the forecast is based on few days of data (new launch), say confidence is lower and ask the human to approve a partial step first.
