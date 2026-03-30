# Start Here

If you want the shortest path to understanding and running this repository, use this order.

## 1. Canonical local database facade

Start with:

- `turboquant_db.showcase.ShowcaseScoredDatabase`

This is the current best local surface because it supports:

- mutable + sealed hybrid queries
- exact, compressed, and reranked modes
- scored hits with metadata
- benchmark-friendly behavior

## 2. Canonical API entrypoint

Start with:

- `src/turboquant_db/api/app.py`

This points to the traced showcase API and is the current best external service surface.

## 3. Quick run commands

```bash
pip install -e .[dev]
python examples/quickstart.py
python scripts/run_showcase_benchmark.py
python scripts/run_quantizer_comparison.py
python scripts/run_extended_benchmark.py
```

## 4. Best benchmark/report scripts

- `scripts/export_benchmark_diagnostics.py`
- `scripts/export_extended_diagnostics.py`

## 5. Best docs after this one

- `docs/canonical-path.md`
- `docs/architecture.md`
- `docs/implementation-plan.md`

## 6. Best tests to inspect first

- `tests/unit/test_local_db.py`
- `tests/unit/test_showcase_scored_db.py`
- `tests/integration/test_traced_showcase_api_client.py`
- `tests/integration/test_traced_showcase_api_edges.py`

## Why this file exists

The repository has a few parallel modules from rapid iteration.

This file marks the shortest high-signal route so new contributors can get moving without wandering through the engine attic first.
