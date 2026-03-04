# Dev-Only Implementation Plan

## Objective

Run fast, iterative development loops for infrastructure visualization while keeping minimal reproducibility metadata.

## Active Workflow

1. `make run-dev COUNTRY=<code>`
2. `make serve-dev`
3. `make ui-dev`
4. `make verify-dev`

Compatibility aliases (`run`, `serve`, `ui`) remain available.

## Runtime Changes

- Pipeline defaults to dev semantics.
- Strict blocking enforcement is disabled in the active path.
- Invariant gate is skipped by default in dev runs.
- Run metadata/hashes remain persisted (`run_id`, `inputs_hash`, `config_hash`, `code_hash`).

## Pointer Contract

- Primary pointer: `data/published/latest-dev`
- Compatibility alias: `data/published/latest` mirrors `latest-dev`
- Serve/API read from dev pointer first, fallback to alias.

## Verification Contract (`make verify-dev`)

Minimum required checks:

- input/schema sanity
- layer compute no-crash
- API payload non-empty for selected scope
- UI smoke

## API Expectations

- Keep `/v1` prefix.
- Include `run_id` in run-backed responses.
- Include pointer/lane context in run status and health responses.

## Documentation and Archive Rules

- Keep `README.md` and `AGENTS.md` aligned with active commands and pointer semantics.
- Archived historical docs live under `archive/docs/`.

## Deferred Hardening Backlog

To be handled later by engineering:

- strict determinism rerun enforcement
- strict promotion lane and explicit promotion command
- strict-only pointer lifecycle and gating
- full blocking publish gate restoration
