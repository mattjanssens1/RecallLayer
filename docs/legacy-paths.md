# Legacy Paths

This repository evolved quickly, so a few thinner or earlier modules still exist beside stronger successors.

## Recommended canonical replacements

### API

Prefer:

- `src/turboquant_db/api/app_best.py`
- `python scripts/run_best_api.py`

Compatibility aliases still exist for older notes and scripts:

- `src/turboquant_db/api/app_observed.py`
- `python scripts/run_observed_api.py`

### Experimental inspection surfaces

Use these only when you specifically want richer or more specialized diagnostics:

- `src/turboquant_db/api/app_inspected.py`
- `src/turboquant_db/api/app_measured.py`

### Local database facade

Prefer:

- `turboquant_db.showcase.ShowcaseScoredDatabase`

### Benchmark runners

Prefer:

- `python scripts/run_canonical_flow.py`
- `python scripts/export_full_ladder.py`
- `python scripts/export_proof_pack.py`

### Why this matters

New contributors should not have to infer which path is current from file names alone.

Use `docs/current-surfaces.md` first, then `docs/api-surface-policy.md`, then this file if you want context on why multiple parallel modules still exist.
