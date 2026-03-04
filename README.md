# Physical Network Infrastructure Map

Dev-first, geometry-first infrastructure mapping with H3.

## Current Mode: Dev Only

This repository is intentionally optimized for fast visual iteration.
Strict reproducibility/promotion guardrails are deferred and tracked as future hardening work.

## Decision Guide

- **I'm exploring**: use the dev loop (`run-dev`, `serve-dev`, `ui-dev`, `verify-dev`).
- **I'm promoting**: not supported in current mode; promotion/repro lane is deferred to engineering hardening.

## Commands

```bash
make run-dev COUNTRY=AR
make serve-dev
make ui-dev
make verify-dev
```

Compatibility aliases are preserved:

- `make run` -> `make run-dev`
- `make serve` -> `make serve-dev`
- `make ui` -> `make ui-dev`

## Fast Loop (Visual Iteration)

```bash
# 1) Run a scoped dev pipeline
make run-dev COUNTRY=AR

# 2) Serve dev data
make serve-dev

# 3) Open UI
make ui-dev

# 4) Validate quickly
make verify-dev
```

Screenshot path convention:

- `artifacts/screenshots/<YYYY-MM-DD>-<short-name>.png`

## Data and Pointer Behavior (Dev)

- Active pointer: `data/published/latest-dev`
- Compatibility alias: `data/published/latest` mirrors `latest-dev`
- Dev exploration must not rely on strict/prod pointer semantics.

## Dev Verification Contract

`make verify-dev` is the minimum required check set:

- input/schema sanity (targeted ingest/unit checks)
- layer compute no-crash (integration run path)
- API payload non-empty for selected scope
- UI smoke

## API Notes

Read endpoints remain under `/v1`.
Run-oriented responses now include pointer/lane context for dev visibility.

## Deferred Hardening (For Engineering)

Not active in current mode:

- strict determinism rerun enforcement
- strict promotion lane and explicit promote command
- strict-only pointer lifecycle (`latest-strict`)
- full blocking gate publish policy

## Archived Docs

Historical handover/planning/log summaries were moved to:

- `archive/docs/HANDOVER.md`
- `archive/docs/HIERARCHICAL_ADAPTIVE_PLAN.md`
- `archive/docs/LOGS.md`
- `archive/docs/NEXT_STEPS.md`

## References

- `docs/PROJECT.md` (authoritative contracts)
- `docs/IMPLEMENTATION_PLAN.md` (current dev-only execution plan)
- `AGENTS.md`
