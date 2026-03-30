# Best API

This is the current best service surface in the repository.

## Canonical entrypoint

- `src/turboquant_db/api/app_best.py`

## Run it locally

```bash
python scripts/run_best_api.py
```

## Tiny in-process demo

```bash
python scripts/demo_best_api_flow.py
```

## What this API gives you

- exact, compressed, and reranked query modes
- scored hits with metadata
- observed-plus trace diagnostics
- mutable vs sealed hit counts
- latency in milliseconds

## When to use it

Use this path whenever you want the clearest current answer to:

- "Which API should I demo?"
- "Which API should I build against first?"
- "Which API has the richest diagnostics right now?"
