# RecallLayer Integration Contract

## Purpose

This document defines the current intended integration contract for **RecallLayer** as a vector retrieval sidecar.

RecallLayer is not the primary system of record for application entities.
Instead:
- the **host application database** remains the source of truth for records and metadata
- **RecallLayer** stores and serves vector retrieval state
- the host application is responsible for hydration, final record reads, and business-level consistency decisions

This contract is meant to make the current prototype more implementable and testable without pretending it already has the guarantees of a fully mature database platform.

## Role boundaries

### Host database responsibilities
The host database owns:
- canonical records
- user-visible metadata
- transactional application state
- auth / tenancy / permissions
- source-of-truth deletes and updates
- final row hydration after retrieval

Examples:
- Postgres
- MySQL
- MongoDB
- document store or application-managed store

### RecallLayer responsibilities
RecallLayer owns:
- vector ids used for retrieval
- embedding payloads or compressed representations
- mutable + sealed retrieval lifecycle
- candidate generation
- approximate and hybrid search execution
- retrieval-facing filter state that is intentionally copied into the sidecar
- storage lifecycle transitions such as flush / compaction / recovery

## Canonical data model

At minimum, each RecallLayer write should contain:
- `vector_id` — stable logical id used to rejoin with the host database
- `embedding` — vector representation to index
- `metadata` — retrieval-relevant metadata copied into RecallLayer
- `embedding_version` — logical version of embedding model or pipeline

### Important boundary

The metadata stored in RecallLayer is **retrieval metadata**, not the complete canonical record.

Examples of good metadata for RecallLayer:
- tenant or account id
- region / locale
- document type
- published / active status
- small ranking or partition hints
- timestamps used for retrieval filters

Examples of data that should remain in the host DB:
- full document body
- transactional fields
- complex relational joins
- permissions model source of truth
- broad application state

## Write contract

### Upsert
The host application may upsert a vector into RecallLayer when:
- a new record is created
- a record's embedding changes
- retrieval-relevant metadata changes

Required behavior:
- latest write for a `vector_id` should become the retrieval-visible version
- RecallLayer may expose the newest write through mutable state before flush
- after flush, visibility may transition from mutable to sealed state
- host applications should treat RecallLayer as eventually lifecycle-settled, not as a transactional peer of the host DB

### Delete
The host application may delete a vector from RecallLayer when:
- the source record is deleted
- the record should no longer be retrievable
- tenancy or visibility state changes in a way that should remove it from search

Required intended behavior:
- delete should mask retrieval visibility for the matching `vector_id`
- latest-write-wins semantics should hold across mutable and sealed state
- physical removal may be deferred to compaction

## Query contract

### Query input
A RecallLayer query may include:
- query embedding
- `top_k`
- optional `candidate_k`
- optional retrieval filters
- optional mode selection such as exact / compressed / rerank path

### Query output
RecallLayer should return at least:
- `vector_id`
- retrieval score
- optional metadata needed for tracing or lightweight routing
- optional debug / trace fields when using diagnostic surfaces

### Important rule
RecallLayer query results are **candidate results**, not fully hydrated business objects.

The host application is expected to:
1. read returned `vector_id`s
2. fetch matching rows from the host database
3. discard stale or non-visible records if host truth disagrees
4. optionally apply downstream reranking or business scoring

## Consistency model

RecallLayer currently fits an **integration-side eventual consistency** model.

That means:
- the host DB remains the canonical authority
- RecallLayer should be kept close to the host DB through application writes or sync jobs
- RecallLayer query visibility is expected to be coherent within its own lifecycle model
- cross-system atomicity with the host DB is **not** currently guaranteed

### What applications should assume today
Applications should assume:
- a write acknowledged by RecallLayer is retrieval-visible according to the current mutable/sealed lifecycle
- flush transitions visibility from mutable to sealed state
- recovery should preserve lifecycle expectations according to current replay watermark rules
- delete masking should obey latest-write-wins semantics in hybrid retrieval paths

Applications should **not** assume today:
- strict cross-system transactions between host DB and RecallLayer
- production-grade checkpoint/WAL semantics equivalent to a mature database engine
- broad distributed consistency guarantees

## Lifecycle contract

### Mutable state
New writes first become visible in mutable state.

### Flush
Flush should:
- seal current live mutable rows into a segment
- add that segment to the active sealed set
- drain flushed mutable rows from runtime mutable state
- avoid creating misleading empty segments on empty flush

### Recovery
Recovery should:
- load sealed state from manifests
- replay only the write-log tail after the shard replay watermark
- rebuild mutable state only for post-watermark writes
- preserve coherent pre-restart vs post-restart visibility as defined by current lifecycle tests

### Compaction
Compaction should:
- replace older active sealed segment sets with newer compacted sealed state
- preserve replay watermark semantics coherently
- avoid moving lifecycle boundaries backwards

### Delete visibility
Delete semantics should follow latest-write-wins behavior:
- if a mutable tombstone exists for `vector_id = X`, sealed rows for `X` should not be query-visible
- physical removal may happen later via compaction

## Host application obligations

The host application should:
- keep `vector_id` stable and unique within its intended retrieval scope
- send retrieval-relevant metadata to RecallLayer
- rehydrate results from the host DB before returning user-facing objects
- tolerate eventual consistency between host DB and RecallLayer
- treat RecallLayer as a retrieval subsystem, not the source-of-truth record store
- ensure tenant/visibility filters are enforced consistently at the application boundary

## Failure and mismatch handling

If RecallLayer and the host DB disagree:
- the host DB wins
- application hydration should drop missing or non-visible rows
- background repair or resync should restore RecallLayer consistency later

Examples:
- RecallLayer returns a `vector_id` whose source row has been deleted → host app discards it
- host row exists but RecallLayer has stale metadata → host app may still hydrate, but retrieval quality may be degraded until reindexed
- host row updated but embedding not yet refreshed → results may be temporarily stale

## Sync patterns

Recommended sync approaches include:

### 1. Inline application writes
App writes to host DB, then writes to RecallLayer.

Best for:
- simple systems
- early product stage
- lower write volumes

Tradeoff:
- not transactional across both systems

### 2. Outbox / event-driven sync
App commits host DB transaction, emits an outbox event, and a worker updates RecallLayer.

Best for:
- more reliable production pipelines
- retryable updates
- separation of write concerns

Tradeoff:
- slightly more delay before retrieval convergence

Concrete local shape now included in this repo:
- `src/turboquant_db/sidecar_sync.py`
- `tests/unit/test_sidecar_sync.py`

That shape is intentionally lightweight, but it makes the intended flow explicit:
- host DB truth is written first
- an outbox event is recorded
- a worker syncs RecallLayer from the event
- repair/backfill remains the drift safety net

### 3. Periodic repair / backfill jobs
A sync job periodically validates and repairs RecallLayer from host truth.

Best for:
- resilience
- bulk migrations
- safety net after deployment issues

## Current non-goals of the contract

This contract does not yet define:
- multi-region replication
- distributed cluster management
- tenant-isolated durability domains
- hard transactional coupling to Postgres or another host DB
- SQL planner integration
- extension-level integration inside Postgres

## Recommended black-box integration tests

The repo now includes a minimal canonical sidecar suite in:
- `examples/postgres_sidecar_flow.py`
- `src/turboquant_db/api/recalllayer_sidecar_app.py`
- `tests/integration/test_recalllayer_sidecar_flow.py`
- `tests/integration/test_recalllayer_sidecar_http_api.py`

That suite currently covers:
- create host row + write to RecallLayer + query returns id
- hydration of candidate ids back through the host DB
- delete/unpublish mirrored into RecallLayer
- flush + restart + recovery preserves expected query visibility
- flush + compaction + restart preserves expected sidecar visibility
- host DB hydration drops missing rows cleanly
- host DB + RecallLayer mismatch path is survivable and repairable

Still useful to add later:
- update embedding + query returns new ranking behavior
- a real Postgres-backed harness when the dependency cost is worth carrying
- higher-volume repair/backfill job orchestration

For repair and rebuild guidance, read:
- `docs/repair-backfill.md`

## Canonical mental model

Treat RecallLayer as:
- a **retrieval index and candidate engine**
- a **search-optimized sidecar**
- a **vector lifecycle subsystem**

Do **not** treat RecallLayer as:
- the primary application record store
- the sole authority on object visibility
- a drop-in replacement for a mature operational database

## Final contract summary

The current intended contract is:

> The application database owns truth. RecallLayer owns vector retrieval. Queries return candidate ids and scores. The application hydrates and validates final records.

That is the clearest integration model for the project at its current maturity.
