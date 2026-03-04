# Agent Handover

Use this document both as a handover checklist and as a reusable transfer prompt.

## Preconditions Before Handover

- Ensure progress tracking file exists at `logs/progress/<YYYY-MM-DD>-<task>.md`.
- Update checklist statuses to reflect current reality.
- Add a final timestamped progress entry immediately before handover.
- Record unresolved blockers with `BLOCKED:` in checklist text.
- Run relevant verification commands and record evidence.

## Required Handover Package

Provide all items below in one handover message/document:

- Objective and scope in one paragraph.
- Current state snapshot:
  - completed items
  - in-progress item
  - blocked items
- Exact changed files list.
- Exact commands run and outcomes.
- Current known issues and risks.
- Explicit next 3-5 actions in order.
- Relevant screenshot paths for UI tasks.
- Mistake replay check summary referencing `logs/mistakes.md`.

## Verification Expectations for Receiving Agent

Receiving agent must:

- Re-read source-of-truth docs (`docs/PROJECT.md`, `docs/IMPLEMENTATION_PLAN.md`, `AGENTS.md`).
- Validate current branch/worktree state (`git status`).
- Re-run the latest claimed verification commands.
- Confirm whether claims in handover match repository state.
- Continue checklist/progress log updates in append-only mode.

## Handover Output Format

Use this structure:

1. Context
2. What is done
3. What is left
4. Evidence
5. Risks and assumptions
6. Immediate next actions

## Reusable Prompt

Copy/paste and fill placeholders.

```text
You are taking over an in-progress task in this repository.

Read first:
- docs/PROJECT.md
- docs/IMPLEMENTATION_PLAN.md
- AGENTS.md
- README.md
- docs/HANDOVER.md
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

## Minimal Example Snippet

```text
Context: Implement multi-layer H3 overlay in UI.
What is done: Added endpoint X and frontend toggle Y.
What is left: Performance guardrails for zoom>=8.
Evidence: pytest tests/ui/test_ui_smoke.py passed; screenshot at artifacts/screenshots/2026-02-28-h3-overlay.png.
Risks and assumptions: Large viewport at high resolution may exceed target render budget.
Immediate next actions: 1) Add resolution cap. 2) Add UI warning. 3) Capture updated screenshot.
```
