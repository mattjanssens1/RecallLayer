# Developer Commands

## Install

```bash
pip install -e .[dev]
```

## Run the best current API

```bash
python scripts/run_best_api.py
```

## Run the canonical workflow

```bash
python scripts/run_canonical_flow.py
python scripts/export_all_reports.py
```

## Run the quickstart

```bash
python examples/quickstart.py
```

## Run selected tests

```bash
pytest tests/unit -q
pytest tests/integration -q
```

## Why this file exists

This is the short command cheat sheet for day-to-day local iteration.
