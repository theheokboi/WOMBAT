# Reusable Prompt: Handover to Another Agent

Copy/paste and fill placeholders.

```text
You are taking over an in-progress task in this repository.

Read first:
- docs/PROJECT.md
- docs/IMPLEMENTATION_PLAN.md
- AGENTS.md
- README.md
- logs/progress/<YYYY-MM-DD>-<task>.md
- logs/mistakes.md

Task objective:
<OBJECTIVE>

Current status:
- Completed:
  - <ITEM>
- In progress:
  - <ITEM>
- Blocked:
  - <ITEM or "none">

Changed files so far:
- <PATH>
- <PATH>

Verification evidence so far:
- <COMMAND> -> <RESULT>
- <COMMAND> -> <RESULT>

UI evidence (if applicable):
- Screenshot(s): <PATH>
- User-reported mismatch: <DESCRIPTION or "none">

Constraints to preserve:
- Determinism and fail-closed publish behavior
- Immutable published artifacts
- Versioned `/v1` API compatibility rules
- Progress log append-only discipline

Your required actions:
1. Re-verify current claims with local commands.
2. Continue from the next unfinished checklist item.
3. Keep changes minimal and test-first.
4. Update progress log at every status transition.
5. Perform mistake replay check before final handoff.

Deliver at handoff:
- concise change summary
- exact tests run and status (blocking/non-blocking)
- remaining risks/assumptions
- next recommended milestone steps
```
