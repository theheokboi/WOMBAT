# AGENTS.md

This file defines conventions for coding agents and human contributors in this repository.

## Mission

Deliver fast, country-scoped, visual iteration for infrastructure mapping while preserving a minimal reproducibility backbone.

Primary reference:

- `docs/PROJECT.md` (authoritative API/data contracts)

## Operating Mode

The repository is currently **dev-only**.

- Exploration speed is prioritized.
- Strict/promotion workflow is deferred to a future hardening phase.
- Do not introduce strict gating assumptions into day-to-day dev commands.

## Non-Negotiable Principles (Current)

- Geometry authority: do not infer spatial membership from free text.
- Explicit run metadata: always persist `run_id`, `inputs_hash`, `config_hash`, `code_hash`.
- Immutable published run directories.
- Dev pointer isolation: use `latest-dev`; keep compatibility alias `latest` in sync.
- Clear internal UX over premature optimization.

## Required Progress Tracking

Progress tracking is mandatory for non-trivial tasks.

- Every task must maintain checklist status markers: `[ ]`, `[~]`, `[x]`.
- Checklist updates must happen during work, not only at the end.
- Blockers must be marked as `BLOCKED: <reason>`.

## Progress Log Requirement

- Path: `logs/progress/<YYYY-MM-DD>-<short-task-name>.md`
- One task per file.
- UTC timestamps.
- Append-only updates.

Required entry format:

```text
## <UTC timestamp>
- Status: <not started|in progress|blocked|complete>
- Checklist item: <reference to item text>
- Update: <what changed>
- Evidence: <test command, output summary, or file path>
- Next: <next concrete action>
```

Minimum cadence:

- task start
- each status transition
- at least once before handoff

## Required Development Sequence

1. Confirm requirement in `docs/PROJECT.md`.
2. Add/update tests for changed behavior.
3. Implement minimal code.
4. Run local verification for impacted paths.
5. Update docs/config examples when behavior/interfaces change.
6. Update `README.md` and `AGENTS.md` for workflow/contract/tooling changes.

## Dev Commands

Primary workflow commands:

- `make run-dev COUNTRY=<code>`
- `make serve-dev`
- `make ui-dev`
- `make verify-dev`

Compatibility aliases:

- `make run` -> `run-dev`
- `make serve` -> `serve-dev`
- `make ui` -> `ui-dev`

## Dev Verification Contract

`make verify-dev` must cover:

- input/schema sanity
- layer compute no-crash
- API payload non-empty for selected scope
- UI smoke

Non-blocking reporting remains required for perf/monitoring checks.

## Data and Publish Rules (Dev)

- Active pointer: `data/published/latest-dev`
- Compatibility alias: `data/published/latest`
- Dev workflow must not assume strict/prod pointer semantics.
- Publish remains atomic for dev pointer updates.
- Never mutate published run artifacts after pointer update.

## API and Serving Rules

- Keep versioned path prefix `/v1`.
- Include `run_id` and layer version context in responses.
- Include lane/pointer context in run/health status payloads for dev visibility.
- Preserve backward compatibility for additive updates.

## Visualization Rules

- Always support facility points and H3 grid layers.
- Use config-driven zoom-to-H3 mapping.
- Avoid heavy client-side geospatial joins.
- Prioritize legibility and provenance in tooltips.

## Visual Verification Protocol

For UI/visual changes:

- run `make run-dev`
- run `make serve-dev`
- verify API payload presence before UI debugging
- run UI smoke tests
- capture at least one screenshot at `artifacts/screenshots/<YYYY-MM-DD>-<short-name>.png`
- log screenshot path and what it proves in progress log

## Documentation Freshness Policy

`README.md` and `AGENTS.md` are living docs.

Any workflow/quality gate/command/contract change must include doc updates in the same change.
If no update is needed, record: `Docs check: no changes required` with rationale in progress log.

## Mistake Tracking and Prevention

- Maintain append-only ledger at `logs/mistakes.md`.
- Log each discovered mistake with root cause, corrective action, prevention rule, and verification.
- Before handoff, run a mistake replay check and record confirmation in progress log.

## Archived Documentation

Historical handover/planning/log summary docs are stored under `archive/docs/`.
Active docs remain in `docs/` (`PROJECT.md`, `IMPLEMENTATION_PLAN.md`).

## Definition of Done (Current Mode)

- Requirement mapped to `docs/PROJECT.md`.
- Tests updated for changed behavior.
- Dev verification completed and reported.
- Docs updated (or explicitly confirmed unchanged with rationale).
- Checklist complete.
- Progress log present with required UTC updates.
