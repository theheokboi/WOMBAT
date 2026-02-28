# Agent Handover Guide

Use this guide when transferring an in-progress task to another coding agent.

## 1. Preconditions Before Handover

- Ensure progress tracking file exists at `logs/progress/<YYYY-MM-DD>-<task>.md`.
- Update checklist statuses to reflect current reality.
- Add a final timestamped progress entry immediately before handover.
- Record any unresolved blockers with `BLOCKED:` in checklist text.
- Run relevant verification commands and record evidence.

## 2. Required Handover Package

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

## 3. Verification Expectations for Receiving Agent

Receiving agent must:

- Re-read source-of-truth docs (`docs/PROJECT.md`, `docs/IMPLEMENTATION_PLAN.md`, `AGENTS.md`).
- Validate current branch/worktree state (`git status`).
- Re-run the latest claimed verification commands.
- Confirm whether claims in handover match repository state.
- Continue checklist/progress log updates in append-only mode.

## 4. Handover Output Format

Use this structure:

1. Context
2. What is done
3. What is left
4. Evidence
5. Risks and assumptions
6. Immediate next actions

## 5. Minimal Example Snippet

```text
Context: Implement multi-layer H3 overlay in UI.
What is done: Added endpoint X and frontend toggle Y.
What is left: Performance guardrails for zoom>=8.
Evidence: pytest tests/ui/test_ui_smoke.py passed; screenshot at artifacts/screenshots/2026-02-28-h3-overlay.png.
Risks and assumptions: Large viewport at high resolution may exceed target render budget.
Immediate next actions: 1) Add resolution cap. 2) Add UI warning. 3) Capture updated screenshot.
```
