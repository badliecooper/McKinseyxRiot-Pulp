---
name: launch-readiness-check
description: Use when a product launch, influencer campaign or promotion is being planned, or when asked whether supply can handle a big marketing push. Stress-tests cover at a demand multiplier before approval.
---
# Launch readiness check

Case gap: marketing set Dragon Passion's launch date and told procurement two weeks before launch.

1. Ask for or assume a stress multiplier. Default: 4x on the flavor, since quick-commerce orders rose about fourfold last spring. State the multiplier as an assumption.
2. Call `find_surplus_and_shortage` and `plan_rebalancing` with `stress` set to `{flavor, multiplier}`.
3. Call `check_upstream_supply` with the same stress. Note ingredient lead times: dragonfruit imports 6-8 weeks, ordered quarterly; passionfruit single cooperative.
4. Verdict, using only tool results:
   - READY: no shortage cells under stress.
   - CONDITIONAL: shortages fixable by transfers or mix shift. List the actions and their cost.
   - NOT READY: residual gap beyond headroom, co-packer and mix shift, or ingredient lead time longer than the time to launch.
5. Recommend the launch date or campaign scale the supply can support, and name who approves (marketing and supply planning together).
6. This is a gate, not a veto. The human decides.
