# Roadmap

## Guiding approach

Build RecallLayer in layers:

1. prove compressed retrieval + rerank quality
2. prove query latency and memory wins
3. harden lifecycle correctness
4. make sidecar integration real
5. improve operational maturity only after the sidecar story is coherent

The goal is not to pretend the project is already a finished database platform.
The goal is to turn it into a believable and testable retrieval subsystem.

## Phase 0: repository and design foundation

### Goals

- define project scope
- document the system architecture
- identify measurable success criteria

### Deliverables

- README
- architecture document
- roadmap
- benchmark plan outline

## Phase 1: baseline benchmark harness

### Goals

- establish an exact-search baseline
- measure recall and latency against a known corpus
- compare compressed-first retrieval plus rerank against exact retrieval

### Deliverables

- dataset loader abstraction
- exact similarity baseline
- top-k evaluation harness
- metrics output for recall@k, latency, memory, and ingest throughput

### Candidate datasets

- public embedding benchmarks
- synthetic corpora for large-scale stress testing
- internal or custom corpora later, if needed

### Exit criteria

- exact baseline reproducible
- benchmark runs scripted and repeatable
- report template available for result snapshots

## Phase 2: compressed retrieval prototype

### Goals

- implement compressed vector representation
- support online writes into a searchable segment
- retrieve top-N candidates from compressed storage
- support rerank-friendly higher-precision paths

### Deliverables

- quantization module interface
- compressed segment format
- simple shard scan or columnar scan query path
- rerank module
- evaluation against baseline

### Exit criteria

- meaningful memory reduction demonstrated
- recall remains acceptable at target candidate_k
- query latency competitive with baseline at target scale

## Phase 3: lifecycle hardening

### Goals

- make flush behavior explicit and testable
- align recovery with lifecycle boundaries
- support deletes and updates coherently
- improve compaction / retirement / replay semantics

### Deliverables

- flush lifecycle contract
- replay-boundary recovery model
- delete masking semantics across mutable + sealed state
- compaction / replay alignment
- lifecycle-focused tests that must stay green

### Exit criteria

- hybrid visibility before vs after restart is coherent
- repeated flushes behave deterministically
- compaction does not break replay boundaries
- delete semantics follow latest-write-wins behavior

## Phase 4: RecallLayer sidecar readiness

### Goals

- define the integration contract clearly
- establish a canonical deployment story beside an existing host DB
- add sidecar-oriented examples and tests
- make the project feel implementable in a real application stack

### Deliverables

- `docs/integration-contract.md`
- `docs/postgres-recalllayer-architecture.md`
- sidecar-first README and start-here docs
- minimal Postgres + RecallLayer example flow
- black-box integration tests for write/query/delete/restart behavior
- repair/backfill note for rebuilding RecallLayer from host DB truth

### Exit criteria

- a new reader can understand the sidecar model quickly
- a Postgres-backed example flow exists
- query results can be hydrated from host ids cleanly
- drift between host DB and RecallLayer is survivable and repairable
- the repo feels like a retrieval subsystem, not just an engine experiment

## Phase 5: indexing, filtering, and operational improvements

### Goals

- reduce candidate generation cost
- improve filtered query performance
- improve service packaging and observability
- harden real deployment ergonomics

### Deliverables

- smarter ANN structures or improved scan planning
- bitmap or posting-list filter acceleration
- clearer HTTP sidecar API packaging
- metrics and operational notes
- deployment guide and troubleshooting notes

### Exit criteria

- p95 query latency improves over earlier retrieval paths
- filter-heavy workloads are benchmarked honestly
- the sidecar API story is operationally believable
- performance and lifecycle behavior are both testable

## Success metrics

Track these throughout the roadmap:

- recall@10, recall@100
- p50, p95, p99 latency
- memory reduction ratio
- storage overhead across mutable, sealed, and compacted states
- rerank cost per query
- ingestion throughput
- filtered-query performance
- lifecycle correctness under flush / restart / compaction
- black-box sidecar integration success rate

## Non-goals for the first serious product-shaping iterations

Avoid these too early:

- pretending to replace the host DB
- premature distributed complexity
- too many ANN variants at once
- over-optimizing before sidecar integration is clear
- building a full SQL engine around the vector path
- claiming production maturity before black-box integration testing exists

## Recommended immediate next files and artifacts

Add or improve these next:

- minimal sidecar example under `examples/`
- repair/backfill doc
- sidecar-oriented integration test slice
- README and docs cleanup for remaining old naming
- optional API contract doc for HTTP write/query surfaces

## Immediate next engineering step

Implement a small canonical sidecar flow that can:

1. write a source record to a host DB model
2. write its vector state into RecallLayer
3. query RecallLayer for candidates
4. hydrate final records by id
5. exercise delete and restart behavior

That becomes the repo's next real heartbeat.