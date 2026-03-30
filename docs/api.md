# API Design

## 1. Goals

The API should be practical for both benchmark usage and future product integration.

It must support:

- collection management
- vector upserts and deletes
- exact metadata filters
- compressed-first query execution
- explainability for debugging
- operational visibility

The first version should be small, explicit, and hard to misunderstand.

## 2. API style

Use HTTP + JSON first.

Why:

- easy to test manually
- easy to wire into benchmark runners
- good enough for early service boundaries

Later, an internal gRPC interface can be added if throughput demands it.

## 3. Core resources

- collections
- vectors
- queries
- traces
- segments
- maintenance jobs

## 4. Collection APIs

### 4.1 Create collection

```http
POST /v1/collections
Content-Type: application/json
```

Request:

```json
{
  "collection_id": "documents",
  "metric": "cosine",
  "embedding_dim": 768,
  "embedding_version": "e5-large-v1",
  "quantizer_version": "tq-v0",
  "rerank_precision": "fp16",
  "filter_schema": {
    "region": "keyword",
    "timestamp": "timestamp",
    "product": "keyword",
    "priority": "int"
  }
}
```

Response:

```json
{
  "collection_id": "documents",
  "state": "active"
}
```

### 4.2 Get collection

```http
GET /v1/collections/{collection_id}
```

### 4.3 List collections

```http
GET /v1/collections
```

### 4.4 Update collection state

```http
PATCH /v1/collections/{collection_id}
```

Allowed updates in early versions:

- state transitions
- quantizer migration intent
- rerank precision policy

## 5. Vector write APIs

### 5.1 Upsert vector

```http
PUT /v1/collections/{collection_id}/vectors/{vector_id}
Content-Type: application/json
```

Request:

```json
{
  "embedding": [0.12, -0.04, 0.77],
  "metadata": {
    "region": "us-east",
    "product": "payments",
    "priority": 2,
    "timestamp": "2026-03-29T10:00:00Z"
  }
}
```

Response:

```json
{
  "vector_id": "doc-123",
  "write_epoch": 1842,
  "visibility": "mutable"
}
```

### 5.2 Batch upsert

```http
POST /v1/collections/{collection_id}/vectors:batchUpsert
```

Use this for benchmark ingestion and bulk loading.

### 5.3 Delete vector

```http
DELETE /v1/collections/{collection_id}/vectors/{vector_id}
```

Response:

```json
{
  "vector_id": "doc-123",
  "deleted": true,
  "write_epoch": 1843
}
```

### 5.4 Get vector metadata

```http
GET /v1/collections/{collection_id}/vectors/{vector_id}
```

Early response should expose logical metadata and visibility state, not raw compressed bytes.

## 6. Query APIs

### 6.1 Search by vector

```http
POST /v1/collections/{collection_id}/query
Content-Type: application/json
```

Request:

```json
{
  "embedding": [0.12, -0.04, 0.77],
  "top_k": 10,
  "candidate_k": 200,
  "filters": {
    "region": {"eq": "us-east"},
    "timestamp": {"gte": "2026-03-01T00:00:00Z"}
  },
  "include_metadata": true,
  "include_trace": false,
  "rerank": true
}
```

Response:

```json
{
  "results": [
    {
      "vector_id": "doc-901",
      "score": 0.913,
      "metadata": {
        "region": "us-east",
        "product": "payments"
      }
    }
  ],
  "request_id": "qry_01"
}
```

### 6.2 Search by document or text later

Keep this out of the core engine for now.

That capability should live in an adapter service that:

1. embeds input content
2. calls the vector query endpoint

### 6.3 Query with explain trace

```http
POST /v1/collections/{collection_id}/query:explain
```

Response should include:

- candidate generation latency
- rerank latency
- segments touched
- candidate counts before and after filters
- optional candidate score samples

## 7. Filter expression model

Keep filters exact and JSON-friendly.

### Supported operators for early versions

- `eq`
- `in`
- `gte`
- `lte`
- `gt`
- `lt`
- `between`

Example:

```json
{
  "product": {"in": ["payments", "risk"]},
  "priority": {"gte": 2},
  "timestamp": {"between": ["2026-03-01T00:00:00Z", "2026-03-31T23:59:59Z"]}
}
```

## 8. Trace APIs

### 8.1 Get query trace

```http
GET /v1/traces/{request_id}
```

Response fields should include:

- request parameters
- candidate counts
- segment list
- latency breakdowns
- final results
- debug metadata if enabled

## 9. Operational APIs

### 9.1 List segments

```http
GET /v1/collections/{collection_id}/segments
```

Useful for:

- debugging compaction
- understanding active generations
- capacity planning

### 9.2 Get shard status

```http
GET /v1/collections/{collection_id}/shards
```

### 9.3 Trigger compaction

```http
POST /v1/collections/{collection_id}/maintenance/compact
```

Request:

```json
{
  "shard_id": "shard-0",
  "reason": "too_many_small_segments"
}
```

### 9.4 Trigger rebuild or migration

```http
POST /v1/collections/{collection_id}/maintenance/rebuild
```

Use this for:

- quantizer upgrades
- embedding-version rebuilds
- format migrations

## 10. Error model

Errors should be explicit and machine-parseable.

Suggested shape:

```json
{
  "error": {
    "code": "INVALID_FILTER",
    "message": "Field 'priority' expected int comparison",
    "details": {
      "field": "priority"
    }
  }
}
```

### Common error codes

- `COLLECTION_NOT_FOUND`
- `VECTOR_NOT_FOUND`
- `INVALID_DIMENSION`
- `INVALID_FILTER`
- `INVALID_METRIC`
- `QUERY_TOO_LARGE`
- `MAINTENANCE_CONFLICT`
- `COLLECTION_NOT_WRITABLE`

## 11. Consistency expectations

### Query consistency

Queries should observe:

- a stable manifest snapshot
- a stable mutable-buffer watermark

### Write consistency

A successful write should return the assigned write epoch.

### Operational consistency

Maintenance endpoints must not expose partially swapped segment states.

## 12. Pagination and limits

List endpoints should support:

- `limit`
- `cursor`

Query endpoints should enforce:

- maximum `top_k`
- maximum `candidate_k`
- maximum batch upsert size

This prevents the API from becoming a clown car full of accidental denial-of-service.

## 13. Authentication and authorization

For internal prototypes, simple service auth is fine.

Longer term, authorization should be scoped by:

- collection access
- write vs read permissions
- maintenance privileges

## 14. Suggested implementation modules

- `api/server.py`
- `api/routes/collections.py`
- `api/routes/vectors.py`
- `api/routes/query.py`
- `api/routes/traces.py`
- `api/routes/maintenance.py`
- `api/schemas.py`

## 15. MVP endpoint set

If we want the smallest useful API, start with only:

- `POST /v1/collections`
- `PUT /v1/collections/{collection_id}/vectors/{vector_id}`
- `DELETE /v1/collections/{collection_id}/vectors/{vector_id}`
- `POST /v1/collections/{collection_id}/query`
- `GET /v1/traces/{request_id}`

That is enough to ingest, query, debug, and benchmark.

## 16. Summary

The API should mirror the engine’s real structure:

- collections define semantics
- writes create logical versions
- queries run compressed retrieval plus rerank
- traces explain what happened
- maintenance manages segment lifecycle

That keeps the service contract aligned with the storage engine instead of pretending the engine is magic behind a curtain.
