# Storage Engine Design

## 1. Objective

Define a storage engine that is:

- append-friendly for online writes
- immutable where possible for search segments
- filter-aware
- measurable under benchmark load
- simple enough for a first implementation
- extensible enough to support future ANN structures

This document focuses on how bytes move through the system, where state lives, and what invariants keep the engine sane.

## 2. Design stance

For the first build, prefer an **LSM-like segment architecture** over in-place mutation.

Why:

- online writes are easier
- immutable sealed segments are simpler to search safely
- compaction handles deletes and updates cleanly
- benchmarkability improves because segment states are explicit

### Engine shape

- mutable in-memory write buffer
- append-only write log for durability
- periodic segment sealing
- immutable compressed search segments
- background compaction and consolidation

## 3. Write path

### 3.1 Upsert flow

1. accept `vector_id`, metadata, and vector
2. validate collection config and embedding dimension
3. append write intent to the write log
4. compute compressed payload and rerank payload
5. place record into the active mutable buffer
6. acknowledge write after durability criteria are met
7. flush mutable buffer into a sealed segment on threshold

### 3.2 Delete flow

1. append tombstone to write log
2. add tombstone to mutable delete buffer
3. expose delete via query-time masking
4. remove physically during compaction

### 3.3 Write acknowledgment modes

Support these modes eventually:

- `log_durable`: ack after write log append
- `segment_visible`: ack after mutable buffer is query-visible
- `sealed`: ack after flush to sealed segment

For MVP, `log_durable` plus query visibility through mutable state is enough.

## 4. Mutable layer

The mutable layer is the realtime buffer.

### Responsibilities

- accept new writes quickly
- provide visibility for recent records
- track tombstones not yet compacted
- expose a scan-friendly view for queries

### Suggested structures

- hash map from `vector_id` to latest mutable record
- append array for scan order
- filter bitmaps or maps for recent metadata
- delete set for visibility masking

### Notes

- keep this layer simple and bounded
- do not let it become a shadow permanent store
- flush by row count, byte size, or time threshold

## 5. Write log

The write log is the durability spine.

### Log contents

- upsert records
- delete tombstones
- collection metadata changes if needed later

### Record fields

- operation type
- write epoch
- vector id
- metadata payload or delta
- embedding payload or reference
- checksum
- timestamp

### Invariants

- write epochs are monotonic per collection
- replay is idempotent
- log order defines conflict resolution within a shard

### MVP recommendation

Use a simple append-only file per collection or shard with periodic checkpoints.

## 6. Segment format

A segment is immutable after sealing.

### Segment contents

- segment header
- compressed vector codes
- residual correction payloads
- local vector id map
- filter indexes
- delete bitmap snapshot if needed
- footer with checksums and offsets

### Header fields

- segment id
- collection id
- shard id
- embedding version
n- quantizer version
- row count
- live row count
- created time
- sealed time

### Footer fields

- offsets to code blocks
- offsets to filter structures
- checksum table
- manifest version

### Layout recommendation

Use a columnar segment layout for the first implementation.

Example:

```text
[header]
[vector_id column]
[code column]
[residual column]
[norm column]
[filter columns / indexes]
[footer]
```

Why columnar first:

- compressed scans become simpler
- filter columns are easier to keep separate
- future SIMD or GPU batching is cleaner

## 7. Segment manifest

The manifest is the source of truth for what segments are searchable.

### Manifest responsibilities

- define active segments for each collection and shard
- define segment generations
- define compaction outputs replacing source segments
- support crash recovery and replay

### Invariants

- queries only search segments present in the active manifest snapshot
- manifest updates are atomic from the reader perspective
- retired segments remain readable until no query references them

### MVP recommendation

Store the manifest as a durable versioned metadata file plus an in-memory cache.

## 8. Query execution model

A query reads from two places:

1. mutable buffer
2. active sealed segments

### Query steps

1. snapshot collection manifest
2. snapshot mutable buffer watermark
3. execute compressed retrieval on mutable layer
4. execute compressed retrieval on sealed segments
5. merge and deduplicate candidates by `vector_id`
6. apply visibility rules and tombstone masking
7. fetch rerank payloads
8. rerank top candidates
9. return final top-k

### Why snapshotting matters

Without a stable read view, concurrent flushes and manifest swaps turn search into a haunted house.

## 9. Candidate generation strategies

The storage engine should allow multiple candidate generation backends.

### Phase 1 backend

- compressed sequential scan by shard or segment

### Phase 2 backends

- IVF over compressed payloads
- graph ANN with compressed node vectors
- GPU batch scan

### Engine rule

The candidate generator must emit a common candidate format:

- vector id
- approximate score
- source segment or mutable tag
- optional debug payload

## 10. Rerank storage

Rerank vectors should be stored separately from compressed search segments.

### Why separate them

- search segments stay dense and hot
- rerank fetches touch only a small candidate set
- warm-tier storage can evolve independently

### Access pattern

- batch fetch by vector ids
- prefer sequential or grouped retrieval by shard
- cache hot rerank vectors aggressively

## 11. Filter execution

Filters must be exact.

### Early implementation

- keyword fields: posting lists or bitmaps
- booleans: bitmaps
- timestamps and numeric ranges: sorted postings or range indexes

### Execution options

- pre-filter candidate search space
- post-filter approximate candidates
- hybrid strategy based on selectivity

### Planner rule

If a filter is highly selective, apply it before expensive rerank expansion.

## 12. Deletes and updates

Treat updates as:

1. tombstone old logical version
2. append new version

### Query-time behavior

- deduplicate by `vector_id`
- keep highest visible write epoch
- ignore tombstoned older versions

### Compaction behavior

- drop superseded rows
- drop tombstoned rows past retention threshold
- rewrite clean segments

## 13. Compaction

Compaction is how the engine pays off write-path debt.

### Goals

- remove deletes and stale versions
- merge small segments
- rebuild filter indexes
- optionally upgrade quantizer versions

### Compaction policy inputs

- too many small segments
- high delete ratio
- poor scan efficiency
- quantizer migration requested

### Compaction outputs

- new sealed segment set
- manifest swap
- retirement schedule for old segments

### Safety rule

Never rewrite active visibility in place. Always produce new segments, then atomically swap manifests.

## 14. Recovery model

On startup:

1. load latest durable manifest
2. load checkpoints if present
3. replay write log after checkpoint watermark
4. rebuild mutable buffer
5. reopen engine for queries and writes

### Recovery invariants

- replay must be idempotent
- manifest must never reference partially written sealed segments
- checksums should detect torn writes or corruption

## 15. Concurrency model

Keep the first concurrency model boring on purpose.

### MVP model

- single writer thread per shard for manifest-changing operations
- concurrent readers with snapshot views
- background compaction with manifest swap

### Why

This narrows the blast radius while the engine is young.

## 16. Failure modes

### 16.1 Segment explosion
Too many tiny segments increase scan and metadata overhead.

Mitigation:

- flush thresholds
- background compaction
- segment-count alarms

### 16.2 Tombstone drag
Deletes accumulate and slow queries.

Mitigation:

- delete ratio thresholds for compaction
- mutable delete masking plus periodic consolidation

### 16.3 Rerank fetch thrash
Warm-tier fetches dominate latency.

Mitigation:

- batch fetches
- cache popular rerank payloads
- co-locate rerank payloads by shard

### 16.4 Recovery ambiguity
Manifest and log disagree after crash.

Mitigation:

- durable manifest versioning
- sealed-segment checksum validation
- log replay from explicit watermarks

## 17. Implementation modules

Suggested modules for code:

- `engine/write_log.py`
- `engine/mutable_buffer.py`
- `engine/segment.py`
- `engine/manifest.py`
- `engine/query_executor.py`
- `engine/compactor.py`
- `engine/recovery.py`

## 18. First build recommendation

Build this in the following order:

1. collection config and manifest
2. write log
3. mutable buffer
4. sealed segment writer and reader
5. exact filter indexes
6. compressed scan executor
7. rerank fetch path
8. compaction and recovery

That order creates a minimally real engine rather than a benchmark toy that collapses on the first delete.

## 19. Summary

The storage engine should behave like a disciplined warehouse:

- writes arrive in an append-friendly dock
- sealed segments become neat shelves
- queries consult a manifest instead of wandering the aisles
- compaction quietly repacks the clutter at night

That is the shape most likely to survive contact with real code.
