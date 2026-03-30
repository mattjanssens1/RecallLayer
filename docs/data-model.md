# Data Model

## 1. Goals

The data model must support:

- compressed-first retrieval
- higher-precision reranking
- online upserts and deletes
- filter-aware search
- versioned embeddings and quantizers
- segment compaction and rebuilds
- future distributed sharding

This is written for a system we expect to actually implement, not just admire from a safe distance.

## 2. Core entities

The first implementation should define these core entities:

1. collection
2. vector record
3. segment
4. shard
5. metadata index
6. query trace
7. maintenance job

## 3. Collection

A collection is the top-level namespace for a searchable embedding corpus.

Examples:

- `support_tickets`
- `documents`
- `products`
- `fraud_events`

### Fields

| Field | Type | Description |
|---|---|---|
| collection_id | string | Stable collection identifier |
| metric | enum | `cosine`, `dot_product`, `l2` |
| embedding_dim | int | Dimension of source embeddings |
| embedding_version | string | Upstream embedding model version |
| quantizer_version | string | Compression pipeline version |
| rerank_precision | enum | `fp32`, `fp16`, `int8` |
| filter_schema | json | Declared metadata fields and types |
| write_epoch | int64 | Monotonic collection-level write counter |
| state | enum | `active`, `migrating`, `read_only`, `archived` |
| created_at | timestamp | Creation time |
| updated_at | timestamp | Last metadata update |

### Invariants

- `metric` and `embedding_dim` are immutable after creation.
- Collections may hold multiple physical segment generations during migration.
- A query always runs against a coherent active collection view.

## 4. Vector record

A vector record is the client-visible logical row.

### Fields

| Field | Type | Description |
|---|---|---|
| collection_id | string | Namespace |
| vector_id | string | Application-defined identifier |
| metadata | json | Filterable and retrievable fields |
| shard_id | string | Assigned shard |
| active_segment_id | string | Current segment containing live compressed payload |
| embedding_version | string | Version of embedding model |
| quantizer_version | string | Version of compression pipeline |
| latest_write_epoch | int64 | Monotonic ordering for conflict resolution |
| is_deleted | bool | Tombstone marker |
| created_at | timestamp | First insert time |
| updated_at | timestamp | Last upsert time |

### Primary key

```text
(collection_id, vector_id)
```

### Notes

- The logical row and the physical payloads are separate.
- Multiple physical versions may exist temporarily during compaction or migration.
- Read visibility is determined by the highest valid `latest_write_epoch` for a given `vector_id`.

## 5. Physical payloads

### 5.1 Compressed payload

Used for candidate generation.

| Field | Type | Description |
|---|---|---|
| segment_id | string | Owning segment |
| local_docno | int32 | Dense segment-local ordinal |
| vector_id | string | Logical row id |
| code | bytes | Main compressed representation |
| residual_bits | bytes nullable | Residual correction channel |
| norm | float nullable | Optional norm or scale |
| filter_row_id | int64 nullable | Pointer into filter structures |
| deleted_bit | bool | Soft delete marker for realtime masking |

### 5.2 Rerank payload

Used only after candidate generation.

| Field | Type | Description |
|---|---|---|
| vector_id | string | Logical row id |
| rerank_vector | bytes | Higher-precision representation |
| precision | enum | `fp32`, `fp16`, `int8` |
| checksum | string nullable | Integrity check |
| warm_tier_ref | string | Storage location reference |

### 5.3 Optional source vector payload

Stored only if we want rebuilds or audits without recomputing embeddings.

| Field | Type | Description |
|---|---|---|
| vector_id | string | Logical row id |
| source_vector | bytes | Original full-precision vector |
| precision | enum | Usually `fp32` |
| cold_tier_ref | string | Storage pointer |

## 6. Segment

A segment is the immutable unit of search storage after sealing.

### Fields

| Field | Type | Description |
|---|---|---|
| segment_id | string | Stable segment id |
| collection_id | string | Parent collection |
| shard_id | string | Owning shard |
| generation | int64 | Monotonic generation number |
| state | enum | `building`, `sealed`, `active`, `compacting`, `retired` |
| row_count | int64 | Live + deleted rows stored |
| live_row_count | int64 | Currently visible rows |
| deleted_row_count | int64 | Tombstoned rows |
| embedding_version | string | Embedding version in segment |
| quantizer_version | string | Quantizer version in segment |
| created_at | timestamp | Build start |
| sealed_at | timestamp nullable | Seal time |
| activated_at | timestamp nullable | Active time |
| min_write_epoch | int64 | Lower bound of writes in segment |
| max_write_epoch | int64 | Upper bound of writes in segment |

### Invariants

- Search segments are immutable once sealed.
- Deletes are represented by tombstones or delete bitmaps until compaction.
- Active segments may coexist across generations during transitions.

## 7. Shard

A shard is the routing and placement unit.

### Fields

| Field | Type | Description |
|---|---|---|
| shard_id | string | Stable shard identifier |
| collection_id | string | Parent collection |
| partition_key | string nullable | Optional routing rule |
| hot_tier_location | string | In-memory or GPU placement |
| warm_tier_location | string | SSD / NVMe placement |
| state | enum | `active`, `draining`, `rebalancing`, `offline` |
| created_at | timestamp | Creation time |

### Notes

- Single-node prototypes can keep one shard.
- The shard abstraction still matters early because it keeps data placement explicit.

## 8. Metadata index

Metadata filters should not live as an afterthought.

### Fields

| Field | Type | Description |
|---|---|---|
| index_id | string | Identifier |
| collection_id | string | Parent collection |
| field_name | string | Metadata field |
| field_type | enum | `keyword`, `int`, `float`, `bool`, `timestamp` |
| index_kind | enum | `bitmap`, `posting_list`, `range_index` |
| backing_segment_id | string | Owning segment |
| cardinality | int64 | Distinct values or bucket count |
| built_at | timestamp | Build timestamp |

### Notes

- Start with exact filter structures.
- Approximation belongs in vector retrieval, not metadata correctness.

## 9. Query trace

A query trace records what happened during retrieval and reranking.

### Fields

| Field | Type | Description |
|---|---|---|
| request_id | string | Query id |
| collection_id | string | Target collection |
| top_k | int | Final result count |
| candidate_k | int | Candidate pool size |
| filters | json | Query filters |
| shards_touched | int | Number of searched shards |
| segments_touched | int | Number of searched segments |
| candidate_generation_ms | float | Approx retrieval latency |
| rerank_ms | float | Rerank latency |
| total_ms | float | Total latency |
| returned_ids | json | Final ids |
| debug_scores | json nullable | Optional debug info |
| created_at | timestamp | Query time |

### Why this matters

When recall falls off a cliff at 2:13 a.m., query traces are how you find the trapdoor.

## 10. Maintenance job

Background work must be modeled directly.

### Fields

| Field | Type | Description |
|---|---|---|
| job_id | string | Unique job id |
| job_type | enum | `compaction`, `rebuild`, `migration`, `rebalance` |
| collection_id | string | Parent collection |
| shard_id | string nullable | Target shard |
| input_segment_ids | json | Source segments |
| output_segment_ids | json nullable | Result segments |
| state | enum | `queued`, `running`, `succeeded`, `failed`, `canceled` |
| started_at | timestamp nullable | Start time |
| finished_at | timestamp nullable | End time |
| error_message | string nullable | Failure context |

## 11. Visibility model

A row is visible to search if:

- its collection is active
- its latest write epoch is not superseded
- it is not tombstoned by a later delete
- its segment is active or otherwise readable during transition

### Practical rule

For MVP, maintain a manifest that defines the active segment set per collection and shard. Query planners must respect the manifest, not the filesystem directory listing.

## 12. Versioning model

There are three distinct version axes:

1. embedding version
2. quantizer version
3. segment generation

Do not collapse these into a single magic number. That is how migrations turn into archaeology.

## 13. First implementation recommendation

For the first code version, keep the following explicit in code:

- `CollectionConfig`
- `VectorRecord`
- `CompressedRecord`
- `RerankRecord`
- `SegmentManifest`
- `ShardManifest`
- `QueryTrace`

These should be serialized in stable formats so benchmark output and on-disk state remain inspectable.

## 14. Summary

The data model separates:

- logical identity from physical payloads
- search storage from rerank storage
- live visibility from background maintenance
- collection semantics from segment mechanics

That separation is the difference between a vector demo and a real storage engine.
