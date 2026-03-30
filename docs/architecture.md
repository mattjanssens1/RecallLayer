# Architecture

## 1. Objective

Design a vector database that:

- stores extremely large embedding corpora efficiently
- preserves high nearest-neighbor recall
- supports online writes
- keeps query latency low
- cleanly separates approximate retrieval from precise reranking

The intended pattern is:

- **Stage A**: retrieve candidates from a compressed search representation
- **Stage B**: rerank top candidates using a higher-precision representation

## 2. Core model

Each logical vector is stored in two layers:

### 2.1 Compressed search representation
Used for first-pass retrieval.

Contains:

- vector identifier
- shard identifier
- compressed code
- residual / correction bits
- optional norm or side statistics
- filter metadata references

This layer is optimized for:

- memory density
- scan or ANN speed
- preserving ranking quality well enough to generate strong candidates

### 2.2 Higher-precision rerank representation
Used only for a short candidate list.

Contains one of:

- fp32 source vector
- fp16 compact exact-ish copy
- int8 or another higher-precision derived representation

This layer is optimized for:

- final ranking quality
- optional auditability
- fallback correctness checks during evaluation

## 3. Service decomposition

### 3.1 Embed service
Responsibilities:

- convert documents / events / items into embeddings
- manage embedding model versioning
- normalize query and item vectors when required by the metric

Inputs:

- raw content or upstream embedding vectors

Outputs:

- embedding vectors
- embedding version metadata

### 3.2 Quantize service
Responsibilities:

- apply the shared transformation pipeline
- generate compressed codes
- generate residual correction data
- write compressed data into the hot index format

Inputs:

- embedding vectors
- quantizer configuration version

Outputs:

- compressed vector records
- optional side statistics

### 3.3 ANN retrieval service
Responsibilities:

- execute first-pass candidate generation against compressed vectors
- support shard-aware search
- support metadata-aware candidate restriction

Possible implementations:

- compressed brute-force scan
- IVF over compressed payloads
- graph ANN with compressed node vectors

Outputs:

- top-N candidate ids
- approximate scores
- debug telemetry for evaluation

### 3.4 Rerank service
Responsibilities:

- fetch higher-precision vector representations for candidates
- compute exact or tighter similarity scores
- optionally fuse vector scores with lexical or business signals

Outputs:

- final top-k results
- rerank latency telemetry

### 3.5 Compaction and maintenance service
Responsibilities:

- rebalance shards
- rewrite segments
- garbage-collect deleted vectors
- migrate between quantizer versions
- compact hot / warm / cold tiers

## 4. Storage tiers

### 4.1 Hot tier
Stores:

- compressed codes
- residual correction bits
- minimal routing metadata

Media targets:

- RAM
- GPU memory for selected shards

Goal:

- maximize searchable corpus in fast memory

### 4.2 Warm tier
Stores:

- fp16 or similar rerank vectors
- recent or frequently accessed metadata

Media targets:

- NVMe / SSD

Goal:

- cheap access to rerank payloads without keeping everything in RAM

### 4.3 Cold tier
Stores:

- fp32 originals if needed
- source artifacts
- archived segments

Media targets:

- object storage

Goal:

- durable retention and offline rebuild support

## 5. Query path

1. Receive query text or vector.
2. Generate or validate the query embedding.
3. Apply the same transformation path used by the compressed index.
4. Search compressed shards for top-N candidates.
5. Apply metadata filters before or during candidate generation where possible.
6. Fetch higher-precision vectors for the candidate set.
7. Rerank the candidate set.
8. Return top-k results.

### 5.1 Query path diagram

```text
Query -> Embed -> Transform/Quant Helper -> Compressed Retrieval -> Top-N Candidates
                                                              |
                                                              v
                                                    Higher Precision Fetch
                                                              |
                                                              v
                                                          Rerank
                                                              |
                                                              v
                                                            Top-K
```

## 6. Ingestion path

1. Accept item id, metadata, and vector.
2. Validate embedding version and metric compatibility.
3. Produce compressed representation.
4. Write compressed record to hot-search storage.
5. Write rerank representation to warm storage.
6. Publish segment update / shard routing metadata.

### 6.1 Design goal for ingestion

The ingestion pipeline should be online and incremental. Large rebuilds should be optional, not the default write path.

## 7. Metadata filtering strategy

Filtering is one of the places approximate systems get tangled.

Recommended strategy:

- partition by high-cardinality or very common filters only when it materially improves performance
- maintain compact posting lists or bitmaps for common filter dimensions
- intersect candidate sets with filters as early as practical
- avoid reranking large filtered sets if compressed retrieval can prune first

## 8. Baseline implementation recommendation

For the first prototype, choose the simplest measurable architecture:

### Recommended first cut

- compressed columnar scan or simple shard scan
- exact rerank on top 100 to 1000 candidates
- offline benchmark harness plus a lightweight online write path

Why this first:

- easier to validate recall and latency
- isolates compression quality from graph or IVF tuning complexity
- creates a clean benchmark baseline for later ANN variants

## 9. API sketch

### 9.1 Write API

```text
PUT /vectors/{id}
{
  "embedding": [...],
  "metadata": {...},
  "embedding_version": "v1"
}
```

### 9.2 Query API

```text
POST /query
{
  "embedding": [...],
  "top_k": 20,
  "candidate_k": 500,
  "filters": {...},
  "rerank": true
}
```

### 9.3 Explain API

```text
GET /query/{request_id}/trace
```

Used for:

- approximate score inspection
- rerank score inspection
- latency breakdowns
- debugging recall regressions

## 10. Observability

Track at minimum:

- recall@k against a truth set
- p50 / p95 / p99 query latency
- compressed index memory footprint
- rerank fetch latency
- ingestion throughput
- shard imbalance
- filter selectivity
- compression ratio by segment

## 11. Failure modes and mitigations

### 11.1 Recall drop from overcompression
Mitigation:

- tune bitrate
- increase candidate_k
- preserve rerank stage
- benchmark per corpus

### 11.2 Filter-heavy query slowdown
Mitigation:

- add bitmap acceleration
- co-partition specific workloads
- add filtered shard routing

### 11.3 Embedding model migrations
Mitigation:

- version embeddings and quantizers independently
- support parallel indexes during migration
- rebuild incrementally

### 11.4 Operational complexity
Mitigation:

- start with secondary index deployment
- keep exact baseline path available for evaluation

## 12. Suggested repository evolution

Next artifacts to add:

1. `docs/benchmark-plan.md`
2. `docs/data-model.md`
3. `docs/api.md`
4. `src/` prototype layout
5. evaluation scripts and sample corpora adapters

## 13. Summary

This system should treat compressed search as the fast front door and higher-precision reranking as the quality lock on the inner gate.

That keeps the design practical:

- approximation where it is safe
- precision where it matters
- online writes
- measurable tradeoffs
