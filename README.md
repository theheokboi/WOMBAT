# WOMBAT

Dev-first, geometry-first infrastructure mapping with H3.

## Quickstart

```bash
COUNTRIES=TW make run-dev
make serve-dev
make ui-dev
make verify-dev
```

Local entrypoints:

- Main UI: `http://localhost:8000/ui/`
- K-rings experiment: `http://localhost:8000/k-rings`
- Health check: `http://localhost:8000/v1/health`

`make verify-dev` is the fast local gate. It aliases `make verify-fast`.

## Repo Map

- `src/`: backend, pipeline, and serving code
- `frontend/`: browser UI and static demo assets
- `configs/`: system and layer configuration
- `scripts/`: maintained operational scripts
- `tests/`: smoke, blocking, and experimental checks
- `docs/`: active documentation
- `archive/`: historical reference only
- `data/`: reference inputs plus local generated run data
- `artifacts/`: local generated outputs only

Generated runtime state such as `data/runs/`, `data/staging/`, `data/published/`, and most of `artifacts/` is local-only and should not drive code review.

## Default Dev Loop

1. `COUNTRIES=TW make run-dev`
2. `make serve-dev`
3. `make ui-dev`
4. `make verify-dev`

Country selection is controlled by `COUNTRIES` as a comma-separated ISO A2 list.

Compatibility aliases remain:

- `make run` -> `make run-dev`
- `make serve` -> `make serve-dev`
- `make ui` -> `make ui-dev`

## Verification Tiers

- `make verify-dev` / `make verify-fast`: fast smoke gate for iteration
- `make verify-ui`: UI shell smoke only
- `make verify-full`: broader regression path
- `make verify-experimental`: perf and property checks

## Contracts And Workflow

- [docs/PROJECT.md](/Users/hyes92121/Desktop/h3-experiment/docs/PROJECT.md): authoritative API, data, and publish contracts
- [docs/ARCHITECTURE.md](/Users/hyes92121/Desktop/h3-experiment/docs/ARCHITECTURE.md): short mental model for run flow and layer dependencies
- [AGENTS.md](/Users/hyes92121/Desktop/h3-experiment/AGENTS.md): contributor and agent workflow rules
- [docs/advanced-workflows.md](/Users/hyes92121/Desktop/h3-experiment/docs/advanced-workflows.md): exports, demo bundles, and graph workflows
- [tests/README.md](/Users/hyes92121/Desktop/h3-experiment/tests/README.md): test tiers and intent
- [scripts/README.md](/Users/hyes92121/Desktop/h3-experiment/scripts/README.md): script catalog with maintained and legacy helpers

## Demo And Export Paths

Static demo bundles are exported into `frontend/demo-data/` and can be hosted without FastAPI. SQLite facility exports are generated into `artifacts/exports/`.

Use the advanced workflows doc for those commands instead of treating them as part of the default dev loop.
