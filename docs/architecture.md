# RecallLayer Architecture

## 1. Objective

RecallLayer is designed as a **vector retrieval sidecar for existing databases**.

Its job is not to replace the application's primary system of record.
Its job is to:
- store retrieval-optimized vector state
- support compressed and hybrid retrieval
- return candidate ids and scores for rerank or hydration
- manage vector lifecycle transitions such as mutable writes, flush, recovery, compaction, and delete visibility

The intended production-shaped pattern is:
- **Stage A**: application truth lives in Postgres or another host database
- **Stage B**: RecallLayer stores retrieval-facing vector state
- **Stage C**: RecallLayer returns candidate ids and scores
- **Stage D**: the application hydrates and validates final records from the host database

## 2. Core system boundary

### 2.1 Host database
The host database owns:
- canonical records
- transactional updates
- auth and permissions truth
- joins and relational structure
- final business-visible state

Examples:
- Postgres
- MySQL
- MongoDB
- application-managed document stores

### 2.2 RecallLayer
RecallLayer owns:
- vector ids
- embeddings or compressed retrieval representations
- retrieval-facing copied metadata
- mutable and sealed retrieval state
- retrieval query execution
- lifecycle transitions such as flush, recovery, and compaction

### 2.3 Application service
The application service coordinates the two systems.

It:
- writes source truth into the host DB
- generates or receives embeddings
- writes vector state into RecallLayer
- issues queries to RecallLayer
- hydrates returned ids from the host DB
- enforces final visibility and business logic

## 3. Core retrieval model

Each logical vector is represented in RecallLayer using a retrieval-oriented two-stage pattern.

### 3.1 Retrieval representation
Used for first-pass candidate generation.

Contains:
- vector identifier
- shard identifier
- compressed code or retrieval payload
- retrieval-facing metadata
- lifecycle metadata needed for storage correctness

Optimized for:
- memory density
- candidate generation speed
- compatibility with hybrid retrieval over mutable + sealed state

### 3.2 Higher-precision ranking path
Used for rerank or exact-ish scoring.

Contains one of:
- full-precision vector
- higher-precision derived representation
- exactish retrieval path over mutable or sealed state

Optimized for:
- final ranking quality
- diagnostics and validation
- quality checks during benchmarking

## 4. Storage lifecycle model

RecallLayer follows an LSM-like storage shape.

### 4.1 Mutable layer
The mutable layer is the online write buffer.

Responsibilities:
- accept recent writes quickly
- expose recent visibility without requiring immediate sealing
- record latest-write-wins state
- hold tombstones before physical cleanup

### 4.2 Sealed segments
Sealed segments are immutable retrieval segments.

Responsibilities:
- store flushed retrieval state
- support stable search surfaces
- provide manifest-driven active visibility
- serve as the durable queryable sealed layer

### 4.3 Manifest-driven active set
The manifest defines which sealed segments are active.

Responsibilities:
- determine searchable sealed state
- support segment replacement through compaction
- give recovery a coherent sealed boundary

### 4.4 Replay boundary and recovery
RecallLayer recovery is intended to:
- load manifest-visible sealed state
- replay only the write-log tail after the replay watermark
- rebuild mutable state only for post-boundary writes
- preserve coherent pre-restart vs post-restart query visibility

### 4.5 Compaction
Compaction is used to:
- replace multiple older sealed segments with newer compacted sealed state
- reduce stale storage debt
- eventually clean up superseded or deleted rows physically
- keep replay boundaries and active ownership coherent

## 5. Query path

The canonical RecallLayer query path is:

1. receive query vector
2. optionally apply retrieval filters
3. search mutable state
4. search active sealed segments
5. merge and deduplicate candidates by `vector_id`
6. enforce latest-write-wins visibility rules
7. optionally rerank with higher-precision scoring
8. return candidate ids and scores

### 5.1 Important visibility rule
If mutable state contains a newer tombstone for a vector id, older sealed rows for that vector id should not remain query-visible.

That rule matters because RecallLayer is intended to behave like a coherent retrieval subsystem, not a haunted pile of half-forgotten segment history.

## 6. Integration architecture

RecallLayer is intended to be used beside an existing database-backed application.

### Canonical pattern

```text
User Query
   -> Application service
   -> query embedding
   -> RecallLayer search
   -> candidate ids + scores
   -> hydrate rows from Postgres
   -> apply final business logic
   -> return results
```

### Canonical write pattern

```text
Application write
   -> commit source row in Postgres
   -> generate embedding
   -> upsert retrieval state into RecallLayer
   -> RecallLayer exposes visibility through mutable state
   -> flush later seals state into active segments
```

## 7. API shape

RecallLayer should expose write/query surfaces shaped around sidecar integration.

### 7.1 Write API
The write API should accept:
- `vector_id`
- embedding payload
- retrieval metadata
- embedding version

### 7.2 Query API
The query API should accept:
- query embedding
- `top_k`
- optional candidate controls
- optional retrieval filters
- optional trace/debug mode

### 7.3 Query output
The query API should return:
- candidate ids
- scores
- optional retrieval metadata
- optional trace data for diagnostics

The query API should **not** be treated as the final source of user-facing application objects.
Hydration remains the job of the application and the host database.

## 8. Deployment shapes

### 8.1 Embedded mode
Good for:
- local development
- benchmarks
- simple demos
- direct Python usage

### 8.2 HTTP sidecar service
Good for:
- realistic application deployments
- language-agnostic integration
- operational separation
- service-level observability

### Recommended approach
Support both, but treat **HTTP sidecar deployment** as the canonical production-shaped story.

## 9. Consistency stance

RecallLayer should currently be described as an **eventually consistent retrieval subsystem** relative to the host database.

That means:
- the host DB remains the truth source
- RecallLayer is kept up to date by application writes or sync workflows
- cross-system atomicity is not guaranteed today
- final hydration and visibility validation remain application concerns

## 10. Observability priorities

RecallLayer should measure at least:
- recall@k
- p50 / p95 / p99 latency
- memory footprint of retrieval state
- rerank cost
- filter selectivity
- lifecycle correctness under flush / recovery / compaction
- mismatch and repair behavior under sidecar integration

## 11. Near-term architectural priorities

To make RecallLayer feel less like a prototype and more like an implementable subsystem, the next architecture-level goals should be:

1. define the integration contract clearly
2. establish the canonical Postgres + RecallLayer architecture
3. add black-box integration tests
4. add a minimal sidecar example flow
5. continue tightening lifecycle invariants for updates, deletes, restart, and compaction

## 12. Summary

RecallLayer should be understood as:
- a retrieval-optimized vector subsystem
- a sidecar beside an existing application database
- a candidate-generation engine with explicit lifecycle behavior

The cleanest mental model is:

> **Postgres keeps the truth. RecallLayer keeps the retrieval index. The application coordinates both.**