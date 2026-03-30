# Best API Demo

If you want the shortest path to a convincing demo, use the best current API.

## Run the API

```bash
python scripts/run_best_api.py
```

## Run the tiny in-process demo

```bash
python scripts/demo_best_api_flow.py
```

## What to point out in a demo

- scored hits with metadata
- exact and reranked approximate modes
- latency in milliseconds
- mutable vs sealed hit counts
- sealed segment ids in the trace

## Why this path

This is the current strongest demo surface in the repository because it combines the most complete diagnostics with the clearest current API entrypoint.
