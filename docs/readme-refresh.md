# Proposed README Refresh

## TurboQuant Native Vector Database

A prototype vector database exploring TurboQuant-style compressed retrieval, hybrid query execution, reranking, and benchmarkable storage-engine ideas.

## Start here

- `docs/start-here.md`
- `docs/public-surface.md`
- `docs/canonical-path.md`

## Best current surfaces

### Local development facade

- `turboquant_db.showcase.ShowcaseScoredDatabase`

### Best API

- `src/turboquant_db/api/app_observed.py`
- `python scripts/run_observed_api.py`

### Best benchmark scripts

- `python scripts/run_showcase_benchmark.py`
- `python scripts/run_quantizer_comparison.py`
- `python scripts/run_extended_benchmark.py`
- `python scripts/export_showcase_bundle.py`
- `python scripts/export_quantizer_bundle.py`
- `python scripts/export_extended_diagnostics.py`

## What the repository already includes

- write log, mutable buffer, and sealed segment runtime
- recovery manager and manifest store
- exact, compressed, reranked, scored, traced, and observed query paths
- small and medium synthetic benchmark fixtures
- Markdown and JSON report exporters
- unit and integration-style tests

## Why this repo stands out

This repository is not only a design document set. It already provides:

- runnable local examples
- a public-facing API path
- benchmark entrypoints
- diagnostics-oriented outputs
- a clear canonical path through the codebase

## Recommended next work

- richer trace metrics in the observed API
- larger benchmark fixtures
- more faithful TurboQuant-like quantization variants
- gradual retirement of thinner legacy surfaces
