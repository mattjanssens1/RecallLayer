# Canonical Postgres + RecallLayer Architecture

## Purpose

This document defines the recommended canonical deployment model for **RecallLayer** in a real application stack.

The goal is not to replace Postgres.
The goal is to make Postgres and RecallLayer play different roles cleanly:
- **Postgres** remains the system of record
- **RecallLayer** becomes the vector retrieval sidecar

This is the most credible near-term architecture for the project.

## One-line architecture summary

> Postgres stores the application truth. RecallLayer stores retrieval-optimized vector state and returns candidate ids for the application to hydrate from Postgres.

## Why this architecture is the canonical one

This architecture is a good fit because:
- most real apps already have Postgres
- application records, joins, permissions, and transactions belong in Postgres
- vector retrieval can evolve independently as a sidecar concern
- RecallLayer can focus on compressed indexing, retrieval, and lifecycle correctness
- the adoption path is much easier than asking users to replace their main database

## High-level architecture

```text
                +----------------------+
                |   Application API    |
                |  (web / backend)     |
                +----------+-----------+
                           |
              writes / reads / hydrate ids
                           |
          +----------------+----------------+
          |                                 |
          v                                 v
+----------------------+         +----------------------+
|       Postgres       |         |     RecallLayer      |
| source of truth DB   |         | vector sidecar       |
| rows, metadata, auth |         | compressed index     |
| transactions         |         | hybrid retrieval     |
+----------------------+         +----------------------+
```

## Component roles

### 1. Application API / backend
The application service is the coordinator.

Responsibilities:
- write source records into Postgres
- obtain or generate embeddings
- write retrieval state into RecallLayer
- send queries to RecallLayer
- hydrate returned ids from Postgres
- enforce application permissions and visibility rules
- handle retries / repair workflows

### 2. Postgres
Postgres is the canonical source of truth.

Stores:
- documents, products, users, listings, or other business entities
- canonical metadata
- relational joins
- permissions / tenancy truth
- application state transitions
- durable business operations

### 3. RecallLayer
RecallLayer is the retrieval subsystem.

Stores:
- `vector_id`
- embedding or compressed representation
- retrieval-facing metadata copied from Postgres/app
- mutable and sealed retrieval state
- segment/manifests/replay lifecycle state

Returns:
- candidate ids
- scores
- optional retrieval diagnostics

## Canonical data flow

### A. Write / ingest flow

```text
App request
   -> write source row to Postgres
   -> generate embedding (inline or async)
   -> upsert vector + retrieval metadata into RecallLayer
   -> query visibility begins in mutable state
   -> later flush seals state into active segments
```

### B. Query flow

```text
User query
   -> application creates query embedding
   -> app sends query to RecallLayer
   -> RecallLayer returns top candidate ids + scores
   -> app fetches matching rows from Postgres
   -> app discards rows that are no longer visible or valid
   -> app returns hydrated results
```

### C. Delete flow

```text
delete / unpublish / revoke visibility
   -> Postgres updates source-of-truth row state
   -> app sends delete or visibility-removing upsert to RecallLayer
   -> RecallLayer masks the vector from retrieval visibility
   -> physical cleanup may happen later via compaction
```

## Recommended synchronization model

### Preferred near-term model: outbox-driven sidecar sync

Recommended pattern:
1. application commits change in Postgres
2. application writes an outbox event in the same transaction
3. worker consumes outbox event
4. worker updates RecallLayer
5. retry on failure
6. periodic repair job reconciles drift

Concrete local shape now included in this repo:
- `src/turboquant_db/sidecar_sync.py`
- `tests/unit/test_sidecar_sync.py`

That module does not claim production durability. It exists to make the intended `host DB truth -> event -> RecallLayer sync` path explicit and testable.

Why this is the best canonical model:
- Postgres remains the truth source
- retries become explicit and durable
- RecallLayer can lag briefly without corrupting source truth
- sidecar sync semantics are easier to test

### Simpler early-stage model: inline dual writes

Pattern:
1. app writes Postgres
2. app writes RecallLayer immediately after

Good for:
- prototype apps
- low-volume systems
- simplest demo and first integration example

Caution:
- not transactional across both systems
- should be backed by retry/repair jobs as maturity grows

## Example canonical schemas

### Postgres source table example

```sql
create table documents (
  id uuid primary key,
  tenant_id uuid not null,
  title text not null,
  body text not null,
  region text,
  status text not null,
  updated_at timestamptz not null default now()
);
```

### RecallLayer vector record example

```json
{
  "vector_id": "doc:3f2b...",
  "embedding": [0.12, -0.44, 0.88, ...],
  "metadata": {
    "tenant_id": "tenant-123",
    "region": "us",
    "status": "published",
    "source_table": "documents"
  },
  "embedding_version": "embed-v1"
}
```

## ID strategy

Use stable ids that can be rehydrated from Postgres directly.

Recommended patterns:
- `document:<uuid>`
- `product:<uuid>`
- `item:<uuid>`

Why:
- prevents collisions across entity types
- makes hydration easy
- improves debugging

## Query / hydration contract

### Query to RecallLayer

Example request:

```json
{
  "embedding": [0.21, -0.18, 0.55],
  "top_k": 20,
  "candidate_k": 100,
  "filters": {
    "tenant_id": { "eq": "tenant-123" },
    "status": { "eq": "published" },
    "region": { "eq": "us" }
  }
}
```

### Example RecallLayer response

```json
{
  "hits": [
    { "vector_id": "document:1", "score": 0.91 },
    { "vector_id": "document:9", "score": 0.88 },
    { "vector_id": "document:4", "score": 0.83 }
  ]
}
```

### Hydration step in the app
The app then:
1. extracts ids from the returned `vector_id`s
2. fetches rows from Postgres
3. drops rows missing from Postgres or no longer visible
4. optionally reorders using returned vector score + business ranking logic

## Visibility and permission model

### Important rule
RecallLayer should not be trusted as the sole source of authorization truth.

Use RecallLayer filters for:
- retrieval narrowing
- tenant partitioning hints
- region/status filtering
- reducing candidate set size

But final application-visible enforcement should still happen in the app or against Postgres truth.

This keeps security and correctness grounded in the source system.

## Reliability model

### If RecallLayer is ahead of Postgres
This should be rare if Postgres is written first.
If it happens, hydration or validation should discard mismatched results.

### If Postgres is ahead of RecallLayer
This is the normal eventual-consistency risk.
Effects:
- recently updated items may rank incorrectly for a short time
- recently deleted items may need host-side filtering until sidecar sync converges
- repair jobs should reconcile drift

## Recovery model in this architecture

RecallLayer recovery matters, but it is not the same as source-of-truth recovery.

Postgres recovery restores business truth.
RecallLayer recovery restores retrieval state.

The current intended RecallLayer lifecycle is:
- mutable writes become query-visible
- flush seals mutable rows into active segments
- recovery replays only the post-watermark write-log tail
- compaction updates sealed ownership while keeping replay boundaries coherent
- delete masking should preserve latest-write-wins behavior across mutable + sealed state

## Recommended black-box tests for this architecture

The repo now includes a lightweight canonical version of this test story in:
- `examples/postgres_sidecar_flow.py`
- `src/turboquant_db/api/recalllayer_sidecar_app.py`
- `tests/integration/test_recalllayer_sidecar_flow.py`
- `tests/integration/test_recalllayer_sidecar_http_api.py`
- `docs/repair-backfill.md`

Covered today:

### 1. Create and retrieve
- insert row into host "Postgres"
- write vector to RecallLayer
- query RecallLayer
- hydrate from the host DB
- assert final result is correct

### 2. Delete visibility
- unpublish row in host DB
- mirror delete into RecallLayer
- query RecallLayer
- ensure stale id is hidden before and after restart

### 3. Flush + compaction + restart
- write multiple vectors
- flush
- compact sealed state
- restart RecallLayer
- query again
- verify results remain coherent

### 4. Drift repair
- intentionally create a mismatch
- rely on host hydration to drop stale ids safely
- run a repair sync
- verify RecallLayer converges back to host truth

Still worth adding later:
- richer update/re-embedding ranking assertions
- a real Postgres-backed harness or adapter once the dependency cost is worth it
- broader repair/backfill job orchestration

## Suggested deployment shapes

### Option A: embedded library inside the app process
Best for:
- local development
- benchmarks
- simple demos

### Option B: HTTP sidecar service next to the app
Best for:
- real deployments
- cleaner operational boundaries
- language-agnostic app integration

### Canonical recommendation
Support both, but make **HTTP sidecar service** the main real-world story.

## Operational boundaries

### Postgres owns
- backup and restore as business truth
- relational migrations
- transaction semantics
- auth / access policy truth

### RecallLayer owns
- retrieval performance tuning
- index lifecycle
- flush / compaction / recovery behavior
- vector storage efficiency
- search diagnostics

## What this architecture is not

This architecture is not:
- a two-phase commit system between Postgres and RecallLayer
- a Postgres extension design
- a claim that RecallLayer replaces Postgres queries or joins
- a promise of fully synchronous cross-system consistency

## Recommended next implementation artifacts

The repo now has:
- a minimal embedded sidecar demo
- a minimal sidecar HTTP app for write/query/repair lifecycle flow
- sidecar-focused integration tests
- a repair/backfill note describing how to rebuild RecallLayer from Postgres truth

The main remaining architecture artifacts are:
- a real Postgres-backed integration harness that talks to a live database
- stronger deployment/observability depth for the HTTP sidecar

The repo now includes an honest adapter boundary in `src/turboquant_db/sidecar.py` as `PsycopgPostgresRepository`, but it still stops short of claiming production-ready Postgres integration.

## Final architecture summary

The canonical production-shaped use of RecallLayer is:

> **Postgres keeps the truth. RecallLayer keeps the vector index. The app coordinates writes, queries RecallLayer for candidates, and hydrates final results from Postgres.**

That is the clearest, most honest, and most implementable architecture for the project right now.
