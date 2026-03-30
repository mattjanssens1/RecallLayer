# Inspected API

The inspected API is an experimental service surface for richer trace breakdowns.

## Run it

```bash
python scripts/run_inspected_api.py
```

## What it adds

Compared with the best current observed-plus path, the inspected API adds fields aimed at deeper debugging and benchmark interpretation, including:

- pre-filter candidate estimate
- post-filter candidate estimate
- search latency in milliseconds
- rerank latency in milliseconds
- total latency in milliseconds

## Why use it

Use this path when you want more detailed timing and candidate-shape information while exploring benchmark behavior and API-level diagnostics.
