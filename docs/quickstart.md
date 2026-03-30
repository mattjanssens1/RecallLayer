# Quickstart

## Install

```bash
pip install -e .[dev]
```

## Run the example

```bash
python examples/quickstart.py
```

## Run the mini benchmark

```bash
python scripts/run_mini_benchmark.py
```

## What it demonstrates

- local vector upserts
- exact and compressed hybrid queries
- flush from mutable state to a sealed segment
- exact metadata filters
- simple exact-vs-compressed benchmark output

## Suggested next hack

Open `src/turboquant_db/engine/showcase_db.py` and replace the current compressed path with a more faithful approximation or rerank step.
