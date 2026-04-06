# Current Surfaces

If you want the shortest path through this repository, start here.

The most useful current framing is:

> **RecallLayer is a vector retrieval sidecar for existing databases.**

These are the current best surfaces for working with that system.

## Best local facade

Use:

- `turboquant_db.showcase.ShowcaseScoredDatabase`

This is the clearest local development surface for:
- hybrid queries over mutable and sealed data
- scored hits with metadata
- compressed plus reranked query behavior
- benchmark-oriented local runs
- understanding retrieval lifecycle behavior in one place

## Best API entrypoint

Use:

- `src/turboquant_db/api/app_best.py`
- `python scripts/run_best_api.py`

Use `app_observed.py` and `run_observed_api.py` only as soft-deprecated compatibility aliases for older notes and scripts.

Use `app_inspected.py` and `app_measured.py` when you explicitly want narrower experimental inspection surfaces.

## Best sidecar HTTP surface

Use:

- `src/recalllayer/api/recalllayer_sidecar_app.py`
- `uvicorn recalllayer.api.recalllayer_sidecar_app:app --reload`

This is the narrow product-shaped service surface for:
- health checks
- host-write plus sidecar sync
- delete and unpublish mirroring
- candidate query plus hydration-shaped responses
- repair/backfill seams
- flush and compaction lifecycle hooks

## Best benchmark flow

Use:

- `python scripts/run_canonical_flow.py`

This is the simplest command when you want the benchmark scripts to run in the intended order.

## Best report export

Use:

- `python scripts/export_full_ladder.py`

This is the broadest export path for the current benchmark ladder.

## Best compact proof artifact

Use:

- `python scripts/export_proof_pack.py`

Use this when you want one small, reproducible benchmark artifact.

## Best example

Use:

- `python examples/postgres_sidecar_flow.py`
- `python examples/postgres_sidecar_live.py`
- `uvicorn recalllayer.api.recalllayer_sidecar_app:app --host 127.0.0.1 --port 8001 --reload`
- `python examples/quickstart.py`

`postgres_sidecar_flow.py` is still the easiest product-shaped example.
`postgres_sidecar_live.py` is the honest local/dev path through a real Postgres `documents` table.
The HTTP sidecar app is the clearest service-shaped surface.
By default it uses an in-memory Postgres-shaped repository harness, but the repo now also includes a live psycopg/Postgres harness for the same sidecar contract.

## Read these next

For orientation:
- `docs/repository-status.md`
- `docs/integration-contract.md`
- `docs/postgres-recalllayer-architecture.md`
- `docs/recalllayer-sidecar-http.md`
- `docs/repair-backfill.md`

For technical details:
- `docs/api-surface-policy.md`
- `docs/deprecations.md`
- `docs/architecture.md`
- `docs/benchmark-proof-pack.md`

## Why this file exists

The repository still contains some older names and parallel surfaces from earlier iteration.
This file is meant to be the singular "start here" map until a future consolidation pass removes more aliases and tightens the remaining gaps around a real Postgres adapter.
