---
name: decision-memory
description: Use before making any recommendation, and whenever the user asks why the agent changed its advice. Reads recent human approvals and rejections and respects them.
---
# Decision memory

1. Before recommending, call `get_recent_decisions`.
2. If a similar recommendation was rejected, read the reason:
   - Reason names a better option (e.g. "co-packer first"): lead with that option this time.
   - Reason is cost or size: offer a smaller or cheaper variant.
   - Reason is unclear: ask the approver what would change their mind. Do not repeat the same recommendation unchanged.
3. If similar ones were approved, keep the same approach and mention the precedent.
4. When the advice changes because of a past decision, say so in one line: "Adjusted because <approver> rejected <id> on <reason>."
5. Past decisions inform ranking and wording. They never override the feasibility checks.
