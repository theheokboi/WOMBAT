# Logs Guide

This repository keeps operational history in append-only logs.

## Where Logs Live

- Task progress logs: `logs/progress/*.md`
- Mistake ledger: `logs/mistakes.md`
- Visual evidence: `artifacts/screenshots/*.png`

## How To View Logs

List available progress logs:

```bash
ls -1 logs/progress | sort
```

Open a specific log:

```bash
sed -n '1,260p' logs/progress/2026-02-28-all-countries-country-coloring.md
```

Show the most recent progress log file:

```bash
ls -1 logs/progress | sort | tail -n 1
```

Review the mistake ledger:

```bash
sed -n '1,260p' logs/mistakes.md
```

List screenshots captured during UI verification:

```bash
ls -1 artifacts/screenshots | sort
```

## High-Value 2026-02-28 Logs

- `2026-02-28-bootstrap-implementation.md`
- `2026-02-28-global-h3-overlay.md`
- `2026-02-28-country-mask-polygon-cells.md`
- `2026-02-28-all-countries-country-coloring.md`
- `2026-02-28-country-mask-exclude-antarctica.md`
- `2026-02-28-checkpoint-handoff.md`

## Testing Process References

The exact blocking/non-blocking commands used throughout logs:

- `make test-blocking`
- `make test-nonblocking`
- `make run`
- `make serve`

Each progress log entry includes timestamped evidence lines with pass/fail outcomes and run IDs.
