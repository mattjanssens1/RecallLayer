# Benchmark Plan

## 1. Purpose

This benchmark plan defines how to evaluate a TurboQuant-inspired vector database that uses:

- compressed-first candidate retrieval
- higher-precision reranking on a short candidate list

The goal is to measure whether the architecture delivers a worthwhile tradeoff across:

- recall quality
- latency
- memory footprint
- ingest throughput
- operational simplicity

## 2. Primary questions

The benchmark suite should answer five questions:

1. How much memory can compressed retrieval save versus an exact baseline?
2. How much recall is lost, if any, at different compression levels?
3. How much query latency improves for realistic corpus sizes?
4. How expensive is reranking as candidate_k changes?
5. How well does the system behave under online ingestion and filtered queries?

## 3. Evaluation strategy

Use a staged evaluation approach.

### Stage A: correctness and recall validation
Compare compressed-first retrieval plus rerank against exact top-k search on the same corpus.

### Stage B: latency and throughput validation
Measure p50, p95, and p99 latency for both baseline and compressed pipelines.

### Stage C: scaling validation
Measure performance as corpus size grows from small benchmark sets to production-like sizes.

### Stage D: operational behavior
Measure ingestion throughput, compaction overhead, and filtered-query behavior.

## 4. Baselines

At minimum, compare against these baselines.

### 4.1 Exact baseline

Reference implementation:

- exact brute-force similarity search over full-precision vectors

Purpose:

- establishes ground truth top-k results
- provides the truth set for recall@k and ranking quality

### 4.2 Conventional compressed baseline

Reference implementations:

- scalar quantization plus rerank
- binary quantization plus rerank

Purpose:

- determine whether the TurboQuant-inspired path is actually better than simpler compression methods

### 4.3 Optional ANN baseline

Reference implementations:

- IVF with higher-precision payloads
- graph ANN such as HNSW or DiskANN-style routing if added later

Purpose:

- compare compressed-first retrieval against common ANN alternatives

## 5. Datasets

Start with a mix of small, medium, and large corpora.

### 5.1 Small correctness dataset

Purpose:

- fast iteration during development
- deterministic debugging of recall and ranking issues

Target scale:

- 10k to 100k vectors

Characteristics:

- known queries
- repeatable exact baseline
- easy local execution

### 5.2 Medium benchmark dataset

Purpose:

- realistic performance profiling on a single machine

Target scale:

- 1M to 10M vectors

Characteristics:

- stable benchmark corpus
- broad enough distribution to expose retrieval-quality weaknesses

### 5.3 Large stress dataset

Purpose:

- identify scaling bottlenecks
- test memory savings and throughput claims

Target scale:

- 100M+ vectors, synthetic or staged expansion if needed

Characteristics:

- may use synthetic embeddings with controlled distributions
- should support throughput and memory stress tests even if recall labels are partial

## 6. Query workloads

The benchmark should not rely on a single query style.

### 6.1 Pure vector similarity queries

Description:

- top-k nearest-neighbor search with no metadata filters

Purpose:

- isolate vector retrieval quality and latency

### 6.2 Filtered vector queries

Description:

- vector search with one or more metadata predicates

Examples:

- product = "payments"
- region = "us-east"
- timestamp within last 30 days

Purpose:

- measure the cost of filtering in a compressed-first system

### 6.3 Ingestion plus query mix

Description:

- concurrent or interleaved writes and queries

Purpose:

- test online ingestion behavior and segment freshness

### 6.4 Batch query workload

Description:

- many queries evaluated together

Purpose:

- see whether compressed scan or GPU execution benefits from batching

## 7. Metrics

Track these metrics for every benchmark run.

### 7.1 Quality metrics

- recall@10
- recall@100
- mean reciprocal rank if applicable
- NDCG@k if graded relevance is available
- top-k overlap with exact baseline

### 7.2 Latency metrics

- p50 query latency
- p95 query latency
- p99 query latency
- candidate generation latency
- rerank latency
- filter application latency

### 7.3 Resource metrics

- compressed index memory footprint
- higher-precision store footprint
- total storage footprint by tier
- compression ratio relative to fp32 baseline
- CPU utilization
- GPU utilization if relevant

### 7.4 Write-path metrics

- vectors ingested per second
- segment flush time
- compaction time
- update and delete overhead

### 7.5 Operational metrics

- shard imbalance
- cache hit ratio for rerank vectors
- filter selectivity distribution
- background maintenance cost

## 8. Experiment matrix

The initial experiment matrix should vary a small number of important knobs.

### 8.1 Core knobs

- compression level or bitrate
- candidate_k
- top_k
- corpus size
- query batch size
- filter selectivity

### 8.2 Example experiment grid

| Experiment | Corpus Size | Compression Level | candidate_k | Filters | Batch Size |
|---|---:|---|---:|---|---:|
| E1 | 100k | low | 100 | none | 1 |
| E2 | 100k | medium | 100 | none | 1 |
| E3 | 100k | aggressive | 100 | none | 1 |
| E4 | 1M | medium | 200 | none | 1 |
| E5 | 1M | medium | 500 | none | 1 |
| E6 | 1M | medium | 500 | light | 1 |
| E7 | 10M | medium | 500 | medium | 1 |
| E8 | 10M | medium | 1000 | medium | 32 |

The first goal is not exhaustive tuning. It is to discover the shape of the tradeoff curve.

## 9. Result reporting format

Each benchmark result should produce a machine-readable summary and a human-readable table.

### 9.1 Machine-readable output

Suggested format:

- JSON per run

Suggested fields:

- dataset
- corpus_size
- embedding_dim
- similarity_metric
- compression_config
- candidate_k
- top_k
- batch_size
- filter_profile
- recall_at_10
- recall_at_100
- p50_ms
- p95_ms
- p99_ms
- memory_bytes_hot
- memory_bytes_warm
- ingest_vectors_per_sec
- notes

### 9.2 Human-readable table

| Run | Dataset | Compression | candidate_k | Recall@10 | Recall@100 | P95 ms | Hot Memory GB | Ingest vec/s |
|---|---|---|---:|---:|---:|---:|---:|---:|
| R1 | small | exact | 100 | 1.000 | 1.000 | 18 | 3.2 | 9,500 |
| R2 | small | compressed-medium | 100 | 0.992 | 0.998 | 9 | 0.8 | 14,200 |

## 10. Acceptance thresholds for the first prototype

These are initial working targets, not hard product promises.

### Prototype success target

- memory reduction of at least 3x in the hot search tier
- recall@10 within 1 to 2 percentage points of the exact baseline on the main medium dataset
- p95 latency improvement over exact search at equal corpus size
- online ingestion working without full index rebuilds

### Stretch target

- hot-tier memory reduction above 5x
- recall@10 degradation under 1 percentage point at practical candidate_k
- strong filtered-query performance without major rerank blowup

## 11. Benchmark harness requirements

The benchmark harness should be easy to rerun and extend.

### Requirements

- deterministic seeds where possible
- exact baseline always available
- pluggable retrieval backends
- pluggable compression implementations
- support for storing run artifacts and summary JSON
- reproducible configuration files for each run

### Suggested structure

```text
benchmarks/
  datasets/
  configs/
  runners/
  reports/
```

## 12. First implementation recommendation

Build the harness around the simplest retrieval path first:

- exact brute-force baseline
- compressed columnar scan prototype
- rerank on full-precision top candidates

This keeps the first comparison clean. It avoids confusing quantization quality with graph or clustering complexity.

## 13. Risks to benchmark validity

### 13.1 Synthetic-only optimism
If the benchmark uses only synthetic data, results may look better than real workloads.

Mitigation:

- include at least one realistic corpus as soon as possible

### 13.2 Exact baseline too slow at large sizes
Ground-truth generation may become expensive.

Mitigation:

- compute exact truth on sampled query sets
- cache exact results for reuse

### 13.3 Filter distribution mismatch
Filtered queries can dominate latency in production.

Mitigation:

- include multiple filter selectivity profiles from the start

## 14. Immediate next tasks

1. Add a repository layout for the benchmark harness.
2. Define a config schema for benchmark runs.
3. Implement the exact baseline runner.
4. Implement a placeholder compressed backend interface.
5. Add a small local dataset adapter for fast iteration.

## 15. Summary

This benchmark plan is the scoreboard for the project.

If the architecture cannot show a compelling curve across recall, latency, and memory, the idea stays a sketch. If it can, the repo graduates from blueprint to engine room.
