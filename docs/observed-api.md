# Observed API

The observed API name is now a **soft-deprecated compatibility alias** for the repository's current best public-facing service path.

## Compatibility entrypoint

- `src/turboquant_db/api/app_observed.py`

## Canonical replacement

- `src/turboquant_db/api/app_best.py`

## Run it locally

```bash
python scripts/run_best_api.py
```

## What it returns

Compared with thinner API variants, the observed API returns richer diagnostics such as:

- scored hits with metadata
- query mode
- filters applied flag
- mutable live count
- sealed segment count
- sealed segment ids
- result count
- rerank candidate count estimate
- latency in milliseconds

## Why this file still exists

Older notes and scripts may still point at the observed name. Keep using it only for compatibility; new usage should prefer the best API path.
