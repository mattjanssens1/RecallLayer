# Observed API

The observed API is the current best public-facing service path in this repository.

## Canonical entrypoint

- `src/turboquant_db/api/app_observed.py`

## Run it locally

```bash
python scripts/run_observed_api.py
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

## Why use this path

If you want to show the project publicly or build on the current best service boundary, this is the API to use first.
