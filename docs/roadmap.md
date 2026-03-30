# Roadmap

## Guiding approach

Build the system in layers:

1. prove compression + rerank quality
2. prove query latency and memory wins
3. add smarter ANN structures
4. harden ingestion, filtering, and operations

The early goal is not elegance. It is evidence.

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

## Phase 2: first compressed retrieval prototype

### Goals

- implement compressed vector representation
- support online writes into a searchable segment
- retrieve top-N candidates from compressed storage
- rerank candidates using higher-precision vectors

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

## Phase 3: indexing and filtering improvements

### Goals

- reduce candidate generation cost
- improve filtered query performance
- scale shard routing and segment management

### Deliverables

- IVF or graph ANN prototype
- bitmap or posting-list filter acceleration
- shard routing policy
- compaction process for segments

### Exit criteria

- p95 query latency improvement over Phase 2
- filter-heavy workloads benchmarked
- no major recall collapse under realistic filters

## Phase 4: ingestion hardening and lifecycle management

### Goals

- make writes durable and incremental
- support deletes and updates cleanly
- support embedding and quantizer version migrations

### Deliverables

- write-ahead ingestion log or equivalent durable queue
- tombstone handling
- background compaction
- multi-version segment support

### Exit criteria

- online ingestion stable under sustained load
- rebuild and recovery path documented
- migration strategy tested

## Phase 5: production-readiness layer

### Goals

- expose clear APIs
- add observability and operational controls
- support deployment in realistic environments

### Deliverables

- query API
- write API
- trace / explain endpoint
- metrics dashboards
- deployment guide
- performance tuning notes

### Exit criteria

- stable benchmark suite in CI or scripted automation
- documented SLO targets
- operational runbook for failures and maintenance

## Success metrics

Track these throughout the roadmap:

- recall@10, recall@100
- p50, p95, p99 latency
- memory reduction ratio
- storage overhead across hot, warm, and cold tiers
- rerank cost per query
- ingestion throughput
- filtered-query performance

## Non-goals for the first iterations

Avoid these too early:

- premature distributed complexity
- too many ANN variants at once
- over-optimizing before benchmarks exist
- building a full SQL engine around the vector path

## Recommended next file to add

`docs/benchmark-plan.md`

That should pin down:

- datasets
- metrics
- baseline methods
- result table format
- first target scale

## Immediate next engineering step

Implement a tiny prototype skeleton that can:

1. ingest vectors
2. encode them into a compressed representation
3. search compressed representations
4. rerank results
5. print benchmark metrics

That gives the repo its first heartbeat.
