# Implementation Plan

## 1. Goal

Turn the design documents into an implementation sequence that minimizes architectural regret.

This plan assumes we will actually build the system, benchmark it, and evolve it from a single-node prototype into a more capable engine.

## 2. Build philosophy

### Principles

- make correctness visible early
- prefer boring storage invariants over clever shortcuts
- isolate compression quality from indexing complexity
- keep exact metadata filters exact
- benchmark before optimizing
- leave room for future distributed execution without forcing it early

### Anti-goals

- do not start with graph ANN
- do not hide mutable state in accidental globals
- do not couple APIs directly to on-disk layouts
- do not invent a magical all-in-one record blob for convenience

## 3. Milestone 0: project skeleton

### Deliverables

- Python package scaffold
- config loading
- domain model classes
- benchmark runner shell
- test harness shell

### Exit criteria

- repository installs locally
- smoke test passes
- benchmark command runs with placeholder backend

## 4. Milestone 1: exact baseline engine

This is the first truly useful milestone.

### Implement

- collection config model
- vector record model
- in-memory exact store
- exact top-k search
- exact filter evaluation
- benchmark runner against exact backend

### Why first

Without an exact baseline, recall numbers become decorative theater.

### Exit criteria

- exact query results are deterministic
- recall truth sets can be generated and cached
- benchmark report captures exact baseline latency and memory

## 5. Milestone 2: write log and mutable buffer

### Implement

- append-only write log
- write epoch assignment
- mutable upsert buffer
- mutable delete handling
- query-time visibility rules over mutable state

### Key invariants

- replay is idempotent
- last visible write epoch wins
- deletes mask prior versions

### Exit criteria

- writes survive restart through log replay
- mutable query path returns correct latest-visible results
- delete visibility tests pass

## 6. Milestone 3: sealed segment format

### Implement

- segment builder
- segment reader
- manifest file format
- segment activation flow
- flush from mutable buffer to sealed segment

### Keep simple

- columnar layout
- sequential compressed scan only
- one shard is acceptable initially

### Exit criteria

- sealed segments are readable after restart
- manifest swaps are atomic from the reader perspective
- queries merge mutable and sealed sources correctly

## 7. Milestone 4: compression abstraction layer

### Implement

- quantizer base interface
- scalar baseline implementation
- binary baseline implementation
- TurboQuant-like placeholder implementation hook

### Interface contract

A quantizer should expose at least:

- `encode(vector) -> compressed_record`
- `approx_score(query, compressed_record) -> float`
- `batch_approx_score(query, code_block) -> array`
- metadata about code size and precision mode

### Exit criteria

- multiple quantizers can run through the same benchmark harness
- exact baseline remains available for truth comparisons

## 8. Milestone 5: compressed scan retrieval

### Implement

- compressed segment scan executor
- candidate heap logic
- merge and deduplicate across mutable and sealed sources
- top-N candidate collection

### Important rule

Do not add ANN graph or IVF yet. Learn the compression curve first.

### Exit criteria

- compressed retrieval works end-to-end
- recall and latency are benchmarked on the medium dataset
- debug traces show candidate quality before rerank

## 9. Milestone 6: rerank path

### Implement

- rerank payload storage
- batch fetch by candidate ids
- exact or higher-precision scoring
- final top-k ordering

### Exit criteria

- rerank improves recall over compressed-only mode
- latency breakdown clearly separates candidate and rerank phases
- warm-tier cache hooks exist even if simple at first

## 10. Milestone 7: filter indexes

### Implement

- bitmap indexes for keyword and boolean fields
- range filtering for numeric or timestamp fields
- query planner for pre-filter vs post-filter execution

### Exit criteria

- filtered queries are correct
- benchmark suite reports filter selectivity and latency
- highly selective filters reduce rerank waste

## 11. Milestone 8: compaction and recovery hardening

### Implement

- segment merge compaction
- tombstone cleanup
- superseded row cleanup
- crash recovery checks
- checksum validation

### Exit criteria

- repeated update/delete workloads remain stable
- query latency does not degrade unbounded with tombstones
- recovery tests pass across flush and compaction boundaries

## 12. Milestone 9: service API

### Implement

- collection endpoints
- upsert and delete endpoints
- query endpoint
- query trace endpoint
- maintenance endpoints

### Exit criteria

- benchmark harness can drive the system through the service API if desired
- responses expose enough telemetry for debugging

## 13. Milestone 10: smarter retrieval backends

Only after the previous milestones are benchmarked.

### Candidate additions

- IVF on compressed payloads
- graph ANN with compressed node vectors
- batch or GPU scoring backend

### Decision rule

Add complexity only if the compressed scan baseline proves the compression tradeoff is promising and scan cost is the next bottleneck.

## 14. First language and framework recommendation

### Recommended starting stack

- Python for prototype and benchmark velocity
- FastAPI for service layer
- NumPy for vector math
- simple local file storage for manifests, logs, and segments

### Why this stack

- fast iteration
- easy benchmark wiring
- enough performance for architectural learning

If the engine later deserves it, hot loops can migrate to Rust, C++, or specialized kernels.

## 15. Suggested initial class list

### Domain

- `CollectionConfig`
- `VectorRecord`
- `CompressedRecord`
- `SegmentManifest`
- `QueryRequest`
- `QueryResult`
- `QueryTrace`

### Engine

- `WriteLog`
- `MutableBuffer`
- `SegmentBuilder`
- `SegmentReader`
- `ManifestStore`
- `QueryExecutor`
- `Compactor`
- `RecoveryManager`

### Quantization and retrieval

- `Quantizer`
- `ScalarQuantizer`
- `BinaryQuantizer`
- `TurboQuantLikeQuantizer`
- `CandidateGenerator`
- `CompressedScanRetriever`
- `Reranker`

## 16. Risks and decision points

### Risk 1
Compression implementation complexity may outpace the rest of the engine.

Mitigation:

- keep `TurboQuantLikeQuantizer` behind a stable interface
- benchmark with scalar and binary baselines first

### Risk 2
Warm-tier rerank storage may dominate latency.

Mitigation:

- batch fetches
- add cache instrumentation early

### Risk 3
Filter handling may become an afterthought and poison real-world results.

Mitigation:

- implement exact filter structures before exotic ANN work

## 17. Definition of success for the prototype

The first meaningful prototype succeeds if it can:

1. ingest vectors online
2. survive restart with correct visibility
3. search sealed and mutable data together
4. return strong recall after rerank
5. demonstrate clear hot-memory savings
6. produce benchmark reports that drive design decisions

## 18. Recommended next coding artifacts

The next files we should actually create in code are:

1. `pyproject.toml`
2. `src/turboquant_db/__init__.py`
3. `src/turboquant_db/model/collection.py`
4. `src/turboquant_db/model/records.py`
5. `src/turboquant_db/model/manifest.py`
6. `src/turboquant_db/benchmark/runner.py`
7. `tests/unit/test_collection_config.py`
8. `tests/unit/test_visibility_rules.py`

## 19. Summary

This plan builds the system like a real database project:

- truth first
- durability second
- immutable search segments third
- compression and rerank fourth
- indexing tricks only after the baseline speaks

That order gives us a fighting chance of ending up with an engine instead of an elaborate benchmark costume.
