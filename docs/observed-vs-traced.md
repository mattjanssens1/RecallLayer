# Observed vs Traced API

This repository currently has both traced and observed API variants.

## Use the observed API by default

Prefer:

- `src/turboquant_db/api/app_observed.py`
- `python scripts/run_observed_api.py`

The observed API is the best current public-facing service path because it returns:

- scored hits with metadata
- latency in milliseconds
- sealed segment ids
- sealed segment counts
- rerank candidate count estimates
- filter flags and result counts

## When to use the traced API

The traced API is still useful as a lighter-weight diagnostic stepping stone, but the observed API is the stronger surface for demos, contributors, and public screenshots.

## Recommendation

If you are updating examples, docs, or tests, prefer the observed path first unless you specifically need the thinner traced version.
