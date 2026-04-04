# Observed vs Traced API

This repository currently has both traced and observed-style API variants.

## Use the best API path by default

Prefer:

- `src/turboquant_db/api/app_best.py`
- `python scripts/run_best_api.py`

The best API is the current strongest public-facing service path because it returns:

- scored hits with metadata
- latency in milliseconds
- sealed segment ids
- sealed segment counts
- rerank candidate count estimates
- filter flags and result counts

`app_observed.py` and `run_observed_api.py` remain as soft-deprecated compatibility aliases for older notes and scripts.

## When to use the traced API

The traced API is still useful as a lighter-weight diagnostic stepping stone, but the best/observed-plus surface is the stronger path for demos, contributors, and public screenshots.

## Recommendation

If you are updating examples, docs, or tests, prefer the best path first unless you specifically need the thinner traced version.
