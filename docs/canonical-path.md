# Canonical Path

If you are new to this repository, use this path first.

## Best database facade

Use:

- `turboquant_db.showcase.ShowcaseScoredDatabase`

This is the current best local development surface because it supports:

- hybrid queries over mutable and sealed data
- scored hits with metadata
- reranked compressed queries
- benchmark-friendly behavior

## Best API surface

Use:

- `src/turboquant_db/api/showcase_server_traced.py`

This is the current best public-facing API because it returns:

- scored results
- metadata
- trace diagnostics
- exact, compressed, and reranked query modes

## Best benchmark entrypoints

Use:

- `scripts/run_showcase_benchmark.py`
- `scripts/run_quantizer_comparison.py`
- `scripts/run_extended_benchmark.py`
- `scripts/export_benchmark_diagnostics.py`

## Best example

Use:

- `examples/quickstart.py`

## Why this file exists

There are a few thinner or earlier modules in the repository from the project’s evolution.

This file marks the current highest-signal path so contributors and visitors do not have to guess which route is the most representative.
