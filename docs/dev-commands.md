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

## Run the RecallLayer HTTP sidecar

```bash
uvicorn recalllayer.api.recalllayer_sidecar_app:app --host 127.0.0.1 --port 8001 --reload
```

## Run the live Postgres sidecar harness

```bash
pip install -e .[dev,postgres]
docker run --rm --name recalllayer-postgres -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=recalllayer -p 5432:5432 postgres:16-alpine
export RECALLLAYER_POSTGRES_DSN=postgresql://postgres:postgres@127.0.0.1:5432/recalllayer
python examples/postgres_sidecar_live.py
pytest tests/integration/test_recalllayer_sidecar_postgres_live.py -q
```

## Run selected tests

```bash
pytest tests/unit -q
pytest tests/integration -q
```

## Why this file exists

This is the short command cheat sheet for day-to-day local iteration.
