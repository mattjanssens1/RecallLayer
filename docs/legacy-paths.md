# Legacy Paths

This repository evolved quickly, so a few thinner or earlier modules still exist beside stronger successors.

## Recommended canonical replacements

### API

Prefer:

- `src/turboquant_db/api/app_observed.py`
- `src/turboquant_db/api/showcase_server_observed.py`

Older traced or showcase API modules may still be useful for reference, but the observed path is the best public-facing surface right now.

### Local database facade

Prefer:

- `turboquant_db.showcase.ShowcaseScoredDatabase`

### Benchmark runners

Prefer:

- `src/turboquant_db/benchmark/showcase_runner.py`
- `src/turboquant_db/benchmark/extended_runner.py`
- `src/turboquant_db/benchmark/quantizer_compare.py`

### Why this matters

New contributors should not have to infer which path is the current best path from file names alone.

Use `docs/start-here.md` first, then `docs/canonical-path.md`, then this file if you want context on why multiple parallel modules exist.
