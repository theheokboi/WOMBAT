# AGENTS.md

This file defines conventions for coding agents and human contributors working in this repository.

## Mission

Build and maintain a deterministic, geometry-first infrastructure mapping system with strong test gates and clear internal visualization.

Primary references:

- `docs/PROJECT.md` (contracts and requirements)
- `docs/IMPLEMENTATION_PLAN.md` (execution blueprint)

When conflicts exist, `docs/PROJECT.md` is authoritative for data/API contracts.

## Non-Negotiable Principles

- Determinism first: identical inputs + config must produce identical outputs.
- Geometry authority: do not infer spatial membership from free-text labels.
- Explicit versioning: persist `run_id`, `inputs_hash`, `config_hash`, `code_hash`.
- Fail-closed publish: never publish when blocking checks fail.
- Immutable artifacts: do not mutate published run directories.
- Simple and clear UX: internal readability over premature performance work.

## Working Mode

- Prefer direct implementation after gathering local context.
- Ask questions only when ambiguity is high-impact and cannot be resolved from repo/docs.
- Keep changes scoped, reviewable, and traceable to a requirement or test.
- Avoid speculative abstractions not needed by current milestones.

## Required Progress Tracking

Progress tracking is mandatory for all non-trivial tasks.

- Every task must have a checklist with explicit status markers:
  - `[ ]` not started
  - `[~]` in progress
  - `[x]` complete
- The checklist must be updated as work progresses, not only at the end.
- Any blocker must be marked in the checklist item text with `BLOCKED:` and a short reason.

## Progress Log Requirement

Each task must maintain a progress log file:

- Path: `logs/progress/<YYYY-MM-DD>-<short-task-name>.md`
- One task per file.
- Use UTC timestamps for entries.
- Append-only updates; do not rewrite history except to correct factual mistakes.

Required entry format:

```text
## <UTC timestamp>
- Status: <not started|in progress|blocked|complete>
- Checklist item: <reference to item text>
- Update: <what changed>
- Evidence: <test command, output summary, or file path>
- Next: <next concrete action>
```

Minimum update cadence:

- At task start.
- At every status transition.
- At least once before handoff/final response.

## Required Development Sequence

1. Confirm requirement in `docs/PROJECT.md`.
2. Add or update tests that define expected behavior.
3. Implement minimal code to satisfy tests and contract.
4. Run local verification for impacted suites.
5. Update docs/config examples if behavior or interfaces changed.
6. Update `README.md` and `AGENTS.md` if workflows, contracts, tooling, or quality gates changed.

Do not skip step 2 for behavior changes.

## Documentation Freshness Policy

`README.md` and `AGENTS.md` are living documents and must reflect current repository reality.

- Any change to developer workflow, quality gates, commands, architecture boundaries, or API/data contracts must include doc updates in the same change.
- If no updates are needed, include an explicit statement in the progress log: `Docs check: no changes required` with justification.
- Documentation drift is treated as a quality issue and blocks completion.

## Mistake Tracking and Prevention

All agents must track mistakes and enforce non-repetition.

- Maintain a mistake ledger at `logs/mistakes.md` (append-only).
- Every discovered mistake (process, implementation, testing, or communication) must be logged with:
  - UTC timestamp
  - short mistake description
  - root cause
  - corrective action taken
  - prevention rule for future tasks
  - verification evidence
- Before final handoff, run a "mistake replay check":
  - review relevant ledger entries
  - confirm current change does not repeat any logged mistake
  - record this confirmation in the progress log
- If a previously logged mistake is about to repeat, stop and correct course before proceeding.
- Repeating a logged mistake without explicit user approval is a workflow violation.

## Testing and Quality Gates

Blocking (must pass before publish path changes are accepted):

- Unit
- Property-based
- Golden regression
- Invariant/publish-gate checks
- Integration

Non-blocking initially (must still be reported):

- UI smoke
- Performance/monitoring

If a test is flaky, fix or quarantine with explicit rationale and tracking note. Do not silently weaken assertions.

## Data and Schema Rules

- Canonical raw input minimum fields:
  - `ORGANIZATION`, `NODE_NAME`, `LATITUDE`, `LONGITUDE`, `SOURCE`, `ASOF_DATE`
- Canonical facility schema must preserve provenance and include:
  - stable IDs
  - record hash
  - configured H3 indices
  - location confidence
- Schema evolution:
  - additive changes are preferred
  - breaking changes require version bump and migration strategy

## Layer and Source Extension Contracts

Layer plugins must implement:

- `spec()`
- `compute(canonical_store, layer_store, params)`
- `validate(artifacts)`

Source adapters must implement:

- `fetch(config)`
- `parse(raw_files)`
- `normalize(records)`
- `source_provenance()`

No implicit plugin/source discovery in production mode. Use explicit config registration.

## API and Serving Rules

- Keep versioned path prefix (`/v1`).
- Include `run_id` and relevant layer version in responses.
- Preserve backward compatibility for additive updates.
- For breaking changes, introduce new major API path.

## Visualization Rules

- Always support display of both:
  - facility points
  - H3 grid layers (metro/country)
- Use stable zoom-to-H3 mapping from configuration.
- Avoid heavy client-side geospatial joins.
- Prioritize legibility: clear legends, layer toggles, provenance in tooltips.

## Visual Development and User Verification Protocol

For any UI/visualization change, agents must verify both technical correctness and user-visible output.

- Required local verification sequence:
  - run pipeline data prep: `make run`
  - run server: `make serve`
  - verify API payload presence for rendered layers/endpoints before debugging UI
  - run UI smoke tests (non-blocking but required reporting)
- Required artifact capture:
  - capture at least one screenshot after each substantive visual change
  - save to `artifacts/screenshots/<YYYY-MM-DD>-<short-name>.png` when possible
  - include screenshot path and what it demonstrates in the progress log
- Required user verification loop:
  - state exactly what changed visually
  - provide direct path(s) to screenshot artifact(s)
  - if user reports mismatch, reproduce and iterate until visual intent matches
- Rendering reliability policy:
  - do not depend on a single fragile rendering path (for example WebGL-only) without a tested fallback
  - confirm rendered feature count is plausible against API/canonical counts when user expects “missing” data
- Debug order for “nothing shown” reports:
  - confirm published run exists
  - confirm API endpoints return non-empty data
  - confirm browser/runtime rendering path loads without critical errors
  - then adjust styling/symbolization/aggregation mode

## Publish Safety Rules

- Publish is atomic:
  - write to staging
  - validate
  - flip `data/published/latest` pointer once
- Never partially publish.
- Never edit published run artifacts after pointer flip.

## Observability Requirements

Each run must emit structured logs and include `run_id`.

Minimum metrics:

- `run_success`
- `run_duration_seconds`
- `facility_count_total`
- `facility_count_by_source`
- `invalid_record_count`
- `layer_compute_duration_seconds` by layer
- `publish_timestamp`

## Current Commands

Repository commands are currently:

- `make run`
- `make calibrate COUNTRY=GB`
- `make serve`
- `make ui`
- `make test-blocking`
- `make test-nonblocking`
- `make test`

These commands are part of the expected workflow and should stay synchronized with implementation changes.

## Code and Commit Conventions

- Prefer small, focused commits aligned to one change intent.
- Keep public interfaces typed and documented.
- Avoid hidden behavior in global state.
- Make configuration explicit; do not auto-tune parameters implicitly.
- Do not introduce destructive filesystem/git operations unless explicitly requested.
- Git checkpoint is required for every non-trivial task before handoff:
  - create at least one commit that captures completed progress
  - record commit hash in the task progress log evidence
  - do not hand off with only uncommitted local changes unless explicitly requested by the user

## Definition of Done (Per Change)

- Requirement mapped to docs or issue.
- Tests updated and passing for impacted behavior.
- No contract drift without schema/API versioning actions.
- Documentation updated where user-facing behavior changed.
- Clear handoff note of what changed, why, and residual risks.
- Checklist fully marked with final statuses.
- Progress log present at required path with timestamped updates.
- `README.md` and `AGENTS.md` reviewed and updated (or explicitly confirmed unchanged with rationale).

## Default Assumptions for Agents

- Internal use context.
- Correctness, reproducibility, and clarity take precedence over optimization.
- Country semantics are dataset-dependent and not geopolitical claims.
- Metro semantics are operational (functional), not administrative boundaries.
