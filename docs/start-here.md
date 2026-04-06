# Start Here

If you want the shortest path to understanding this repository, start by thinking of it this way:

> **RecallLayer is a vector retrieval sidecar for existing databases.**

That is the clearest current framing for the project.

## 1. Read the product-shaped story first

Start with these docs in order:

1. `docs/repository-status.md`
2. `docs/current-surfaces.md`
3. `docs/integration-contract.md`
4. `docs/postgres-recalllayer-architecture.md`
5. `docs/recalllayer-sidecar-http.md`
6. `docs/repair-backfill.md`
7. `docs/benchmark-proof-pack.md`

If you want the repositioning rationale itself, then read:
- `docs/recalllayer-repositioning-plan.md`

## 2. Canonical local database facade

Start with:

- `turboquant_db.showcase.ShowcaseScoredDatabase`

This is the current best local surface because it supports:
- mutable + sealed hybrid queries
- exact, compressed, and reranked modes
- scored hits with metadata
- benchmark-friendly behavior

## 3. Canonical API entrypoint

Start with:

- `src/turboquant_db/api/app_best.py`
- `python scripts/run_best_api.py`

Use older app variants only when you explicitly want narrower experimental surfaces or compatibility behavior.

If you want the product-shaped sidecar surface instead of the benchmark/demo API surface, use:

- `src/recalllayer/api/recalllayer_sidecar_app.py`
- `uvicorn recalllayer.api.recalllayer_sidecar_app:app --reload`

## 4. Quick run commands

```bash
pip install -e .[dev]
python examples/postgres_sidecar_flow.py
uvicorn recalllayer.api.recalllayer_sidecar_app:app --reload
python examples/quickstart.py
python scripts/run_best_api.py
python scripts/run_canonical_flow.py
python scripts/export_proof_pack.py
```

The sidecar example and sidecar HTTP app are the most product-shaped local walkthroughs.
They demonstrate host-truth writes, sidecar sync, candidate retrieval, hydration, delete/unpublish handling, repair/backfill seams, and restart/compaction behavior.

When you want the same flow against a live local Postgres instead of the in-memory harness, run:

```bash
pip install -e .[dev,postgres]
docker run --rm --name recalllayer-postgres -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=recalllayer -p 5432:5432 postgres:16-alpine
export RECALLLAYER_POSTGRES_DSN=postgresql://postgres:postgres@127.0.0.1:5432/recalllayer
python examples/postgres_sidecar_live.py
pytest tests/integration/test_recalllayer_sidecar_postgres_live.py -q
```

## 5. Best docs after this one

Read these next depending on what you care about:

### If you care about product/integration direction
- `docs/integration-contract.md`
- `docs/postgres-recalllayer-architecture.md`
- `docs/repair-backfill.md`
- `docs/recalllayer-repositioning-plan.md`

### If you care about engine/lifecycle behavior
- `docs/architecture.md`
- `docs/storage-engine.md`
- `docs/flush-lifecycle.md`
- `docs/compaction.md`
- `docs/recovery-lifecycle.md` *(if/when added later)*

### If you care about benchmarks and proof
- `docs/benchmark-proof-pack.md`
- `docs/benchmark-guide.md`
- `docs/reviewer-summary.md`
- `docs/prove-it-works.md`

## 6. Best tests to inspect first

For broad orientation:
- `tests/unit/test_local_db.py`
- `tests/unit/test_showcase_scored_db.py`
- `tests/unit/test_flush_lifecycle.py`
- `tests/unit/test_recovery_lifecycle.py`
- `tests/unit/test_compaction_recovery_lifecycle.py`

For API behavior:
- `tests/integration/test_recalllayer_sidecar_flow.py`
- `tests/integration/test_recalllayer_sidecar_http_api.py`
- `tests/integration/test_best_api_health_and_flush.py`
- `tests/integration/test_best_api_filters.py`
- `tests/integration/test_best_api_trace_latency.py`

## 7. Current honest mental model

The most useful way to read the repo today is:
- Postgres or another application DB keeps the truth
- RecallLayer keeps vector retrieval state
- RecallLayer returns candidate ids and scores
- the application hydrates final rows and enforces final visibility rules

## Why this file exists

The repository has evolved through several phases and naming layers.
This file is the shortest high-signal route through the current project so a new reader does not have to wander through the engine attic before understanding what the thing actually wants to be.
