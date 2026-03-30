# Measured API

This API exposes engine-native hybrid query inspection.

## Canonical entrypoint

- `src/turboquant_db/api/app_measured.py`

## Run it locally

```bash
python scripts/run_measured_api.py
```

## Tiny in-process demo

```bash
python scripts/demo_measured_api_flow.py
```

## What this API gives you

- exact, compressed, and reranked hybrid query modes
- engine-measured candidate counts before and after filter evaluation
- measured rerank latency instead of a derived estimate
- mutable versus sealed hit counts in the final top-k
- a focused surface for validating the engine inspection path

## Why it exists

Use this path when you want to validate the engine-native inspection work without
changing the current `app_best` alias yet.
