# RecallLayer

**RecallLayer is a vector retrieval sidecar for existing databases.**

It is an early but increasingly disciplined retrieval engine focused on:
- compressed vector indexing
- hybrid retrieval across mutable and sealed state
- rerank-ready candidate generation
- storage lifecycle correctness for flush, recovery, compaction, and delete visibility

The intended production-shaped use case is:
- your primary database remains the source of truth
- RecallLayer manages vector retrieval state
- RecallLayer returns candidate ids and scores
- your application hydrates final records from the source database

## Benchmark results

Measured on a 5 000-vector, 128-dim fixture with scalar int8 quantization and segment cache enabled:

| Query path | Latency | vs exact | Recall@10 |
|---|---|---|---|
| exact-hybrid | ~285 ms | — | 1.0 |
| compressed-hybrid | ~177 ms | 1.6x faster | 1.0 |
| compressed-hybrid + IVF | ~47 ms | **6x faster** | 1.0 |

IVF uses a v2 clustered segment format — k-means runs at flush time, centroids and per-cluster byte offsets are stored in the segment header. At query time, IVF reconstruction is O(n_clusters) with no k-means, and only the probed cluster rows are scored.

Run it yourself:

```bash
python scripts/run_sprint5_benchmark.py
```

## What RecallLayer is

RecallLayer is best understood as:
- a compressed vector retrieval layer
- a search sidecar for existing systems
- a retrieval engine for semantic search, RAG, and recommendation workloads

It is **not** best understood today as:
- a full standalone database replacement
- a mature production vector database platform
- a complete replacement for Postgres, MongoDB, or another system of record

## Best current use case

The clearest use case right now is:

**Postgres + RecallLayer**

In that model:
- Postgres stores canonical rows, permissions, transactions, and metadata truth
- RecallLayer stores vector retrieval state and retrieval-facing metadata
- queries return candidate ids and scores
- the application rehydrates rows from Postgres and applies final business logic

## Start here

If you want the shortest path through the repo, read these first:

- `docs/start-here.md`
- `docs/repository-status.md`
- `docs/current-surfaces.md`
- `docs/integration-contract.md`
- `docs/postgres-recalllayer-architecture.md`
- `docs/recalllayer-sidecar-http.md`
- `docs/repair-backfill.md`
- `docs/postgres-live-harness.md`
- `docs/benchmark-proof-pack.md`

## Best current surfaces

- **Best local facade:** `recalllayer.engine.showcase_scored_db.ShowcaseScoredDatabase`
- **Best benchmark workflow:** `python scripts/run_canonical_flow.py`
- **Sprint 5 benchmark:** `python scripts/run_sprint5_benchmark.py`
- **Best report export:** `python scripts/export_full_ladder.py`
- **Best compact proof artifact:** `python scripts/export_proof_pack.py`

## Quick start

```bash
# 1. Clone & install
git clone https://github.com/mattjanssens1/RecallLayer.git
cd RecallLayer
pip install -e .[dev]

# 2. Run the sidecar-shaped example
python examples/postgres_sidecar_flow.py

# 3. Run the smaller engine quickstart
python examples/quickstart.py

# 4. Run the canonical benchmark flow
python scripts/run_canonical_flow.py

# 5. Run the sprint 5 IVF benchmark
python scripts/run_sprint5_benchmark.py

# 6. Export one compact proof table
python scripts/export_proof_pack.py
```

## Canonical sidecar example

For the current product-shaped story, start with:

- `python examples/postgres_sidecar_flow.py`
- `tests/integration/test_recalllayer_sidecar_flow.py`

Those surfaces intentionally use an in-memory Postgres-shaped repository harness so the sidecar contract is easy to run locally:
- host DB remains truth
- source rows are written there first
- RecallLayer receives vector state second
- RecallLayer returns candidate ids
- the application hydrates final rows from the host DB
- unpublish/delete is mirrored into RecallLayer
- repair/backfill flows are explicit
- restart/recovery and compaction are exercised against persisted RecallLayer state

There is now also a live local/dev Postgres harness using the existing `recalllayer.sidecar.PsycopgPostgresRepository` path:
- `python examples/postgres_sidecar_live.py`
- `tests/integration/test_recalllayer_sidecar_postgres_live.py`

Install the extra dependency and point the harness at a real Postgres DSN:

```bash
pip install -e .[dev,postgres]
docker run --rm --name recalllayer-postgres -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=recalllayer -p 5432:5432 postgres:16-alpine
export RECALLLAYER_POSTGRES_DSN=postgresql://postgres:postgres@127.0.0.1:5432/recalllayer
python examples/postgres_sidecar_live.py
pytest tests/integration/test_recalllayer_sidecar_postgres_live.py -q
```

## What this repo is trying to prove

This repository is trying to prove that a focused retrieval sidecar can be built with:
- coherent hybrid retrieval across mutable and sealed state
- explicit storage lifecycle semantics
- compressed-first retrieval plus rerank-friendly design
- benchmarkable and inspectable query surfaces
- a realistic path toward integration with an existing database-backed application

## Current honest status

This project already contains meaningful engine work around:
- write log + mutable buffer behavior
- sealed segment lifecycle with v2 clustered IVF format
- manifest-driven active state
- recovery replay boundaries
- compaction / retirement / garbage collection
- exact, compressed, hybrid, reranked, and scored query paths
- benchmark and proof workflows

It is still early in areas such as:
- production durability depth beyond the local/dev Postgres harness
- operational maturity as a deployable product
- large realistic workload validation

## Integration-first docs

If you want the product-shaped story instead of just the engine story, read:

- `docs/recalllayer-repositioning-plan.md`
- `docs/integration-contract.md`
- `docs/postgres-recalllayer-architecture.md`
- `docs/recalllayer-sidecar-http.md`
- `docs/postgres-live-harness.md`
- `docs/repair-backfill.md`

## Bottom line

The strongest way to evaluate RecallLayer today is:
1. run the sprint 5 benchmark — compressed retrieval with IVF is 6x faster than exact at 5k vectors with full recall
2. run the canonical flow and inspect the proof outputs
3. read the integration contract
4. read the Postgres + RecallLayer sidecar architecture
5. judge it as a retrieval subsystem for existing stacks, not as a full database replacement
