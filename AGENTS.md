# AGENTS.md

This file defines conventions for coding agents and human contributors in this repository.

Primary contract reference: `docs/PROJECT.md`

## Working Mode

- The repository is dev-first.
- Prefer the shortest loop that validates the changed behavior.
- Do not introduce strict or prod-only workflow assumptions into routine development.

## Context Preservation

- Delegate scoped discovery when it reduces main-thread context pressure.
- Keep synthesis and final decisions in the main thread.

## Non-Negotiable Principles

- Geometry authority: do not infer spatial membership from free text.
- Every run must persist `run_id`, `inputs_hash`, `config_hash`, and `code_hash`.
- Published run directories are immutable after pointer update.
- Dev pointer isolation: `latest-dev` is primary and `latest` is a compatibility alias.
- Prefer clear internal UX over premature optimization.

## Development Sequence

1. Confirm the relevant contract in `docs/PROJECT.md`.
2. Add or update the smallest useful tests.
3. Implement the minimal code change.
4. Run the narrowest verification tier that covers the change.
5. Update docs when workflow, commands, or contracts change.

## Verification Tiers

- `make verify-dev` / `make verify-fast`: default local smoke gate
- `make verify-ui`: UI shell smoke
- `make verify-full`: broader regression path
- `make verify-experimental`: perf and property checks

Use broader tiers only when the change justifies them.

## Progress Tracking

Substantial tasks still need checklist tracking with `[ ]`, `[~]`, and `[x]`.
Blockers should be written as `BLOCKED: <reason>`.

Committed progress logs are required only for:

- contract changes
- publish or data-shape changes
- multi-session investigations
- explicit handoff work

Routine bugfixes, refactors, and UI iteration may keep notes locally and untracked.

When a committed progress log is needed:

- Path: `logs/progress/<YYYY-MM-DD>-<short-task-name>.md`
- Use UTC timestamps
- Keep entries append-only

Entry format:

```text
## <UTC timestamp>
- Status: <not started|in progress|blocked|complete>
- Checklist item: <reference to item text>
- Update: <what changed>
- Evidence: <test command, output summary, or file path>
- Next: <next concrete action>
```

## UI Verification

For real UI or visual behavior changes:

- run the backend path needed for the affected view
- verify the relevant API payloads before debugging the browser
- run `make verify-ui`
- capture a screenshot only when it proves a visual claim

Screenshot convention:

- `artifacts/screenshots/<YYYY-MM-DD>-<short-name>.png`

## Documentation Policy

- `docs/PROJECT.md` owns contracts
- `README.md` is the quickstart
- `AGENTS.md` owns workflow rules

Do not duplicate contract detail across those files. Link to the owner instead.

## Repo Hygiene

- Keep generated runtime output out of code review when possible.
- `src/inframap.egg-info/`, caches, derived artifacts, screenshots, and local run data are not source-of-truth.
- `archive/` is reference material, not active workflow.
- Use `make archive-progress-logs` to move stale committed progress logs into `archive/logs/progress/`.

## Mistake Tracking

- Keep `logs/mistakes.md` append-only.
- Record real regressions, root causes, prevention rules, and verification.
- Before handoff, perform a mistake replay check when the task touched a previously failing area.
