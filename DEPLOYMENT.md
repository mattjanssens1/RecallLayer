# RecallLayer Deployment Guide

RecallLayer is a vector retrieval sidecar — it runs alongside an existing database (typically PostgreSQL) and handles all vector search.  It is **not** a standalone database replacement.

## Quick start with Docker Compose

```bash
# 1. Clone and enter the repo
git clone https://github.com/mattjanssens1/RecallLayer.git
cd RecallLayer

# 2. (Optional) copy .env.example and set your values
cp config/config.yaml.example .env
#    Edit .env: set RECALLLAYER_API_KEY, POSTGRES_PASSWORD, etc.

# 3. Start Postgres + RecallLayer
docker compose up -d

# 4. Check health
curl http://localhost:8765/healthz
# → {"status":"ok"}

# 5. Check status (segments, delete ratio, mutable buffer)
curl http://localhost:8765/v1/status
```

## Architecture

```
┌──────────────────────┐        ┌───────────────────────────┐
│      Application     │        │        PostgreSQL          │
│  (writes + queries)  │───────▶│  canonical document store │
└──────────┬───────────┘        └───────────────────────────┘
           │                              ▲
           │ vector upsert / search       │ hydrate (fetch full docs)
           ▼                              │
┌──────────────────────────────────────────────────────────┐
│                  RecallLayer Sidecar                      │
│  mutable buffer → sealed segments → compressed search    │
└──────────────────────────────────────────────────────────┘
```

**Write flow:** application calls `POST /v1/upsert` → RecallLayer writes to WAL and mutable buffer → periodic `POST /v1/flush` seals the buffer into a segment.

**Query flow:** application calls `POST /v1/query` → RecallLayer searches mutable + sealed state → returns ranked vector IDs → application fetches full documents from PostgreSQL by ID.

## Environment variables

See `config/config.yaml.example` for a full annotated list.  Key variables:

| Variable | Default | Description |
|---|---|---|
| `RECALLLAYER_SIDECAR_ROOT_DIR` | `.recalllayer_sidecar_http_db` | Segment storage path — **must be a durable volume** |
| `RECALLLAYER_COLLECTION_ID` | `recalllayer-sidecar-demo` | Logical collection name |
| `RECALLLAYER_HOST_REPOSITORY` | `inmemory` | `inmemory` or `postgres` |
| `RECALLLAYER_POSTGRES_DSN` | _(none)_ | PostgreSQL DSN (required when `HOST_REPOSITORY=postgres`) |
| `RECALLLAYER_API_KEY` | _(none)_ | Enable `X-Api-Key` auth if non-empty |
| `RECALLLAYER_PORT` | `8765` | HTTP port |
| `RECALLLAYER_AUTO_FLUSH_INTERVAL_SECONDS` | _(none)_ | If set, the sidecar flushes the mutable buffer automatically on this interval (seconds). Useful when the application does not call `POST /v1/flush` itself. |

## Operational runbook

### Startup and recovery

RecallLayer recovers automatically on startup.  It reads the shard manifest to determine the last flush watermark and replays only the post-flush WAL tail into the mutable buffer.  No manual steps are needed after clean or unclean shutdown.

If you suspect manifest/segment drift:

```bash
curl -X POST http://localhost:8765/v1/repair
```

### Flush (sealing the mutable buffer)

Flushes can be triggered automatically or by the caller.

**Automatic flushing** — set `RECALLLAYER_AUTO_FLUSH_INTERVAL_SECONDS` and the sidecar
will flush the mutable buffer on that interval without any application-side plumbing:

```bash
export RECALLLAYER_AUTO_FLUSH_INTERVAL_SECONDS=300  # flush every 5 minutes
```

**Caller-triggered** — recommended when you want deterministic flush boundaries:
- After every N upserts (e.g. 10 000)
- On a periodic schedule (e.g. every 5 minutes)

```bash
# Flush with a specific segment ID and generation
curl -X POST http://localhost:8765/v1/flush \
  -H "Content-Type: application/json" \
  -d '{"segment_id": "seg-20260406-001", "generation": 1}'
```

After a flush:
- The mutable buffer is drained to disk as a sealed segment
- The WAL is truncated (stays bounded)
- The segment is immediately queryable

### Compaction (merging segments)

Run compaction when:
- Segment count exceeds ~10 (check `GET /v1/status`)
- Delete ratio exceeds 0.2 (tombstoned rows waste disk and query time)

```bash
curl -X POST http://localhost:8765/v1/compact \
  -H "Content-Type: application/json" \
  -d '{"output_segment_id": "seg-compacted-001", "generation": 2}'
```

Compaction:
- Merges all active sealed segments into one
- Physically removes tombstoned rows
- Updates the shard replay watermark so recovery stays correct

### Checking status

```bash
curl http://localhost:8765/v1/status | python3 -m json.tool
```

Key fields in the response:
- `segment_count` — number of active sealed segments
- `mutable_buffer_size` — number of un-flushed vectors
- `delete_ratio` — fraction of rows that are tombstoned (trigger compaction above 0.2)
- `replay_from_write_epoch` — WAL replay cutoff (advances after each flush/compaction)

### Prometheus metrics

RecallLayer exposes a Prometheus-compatible metrics endpoint with no external dependency:

```bash
curl http://localhost:8765/metrics
```

Metrics exposed:
- `recalllayer_segment_count` — active sealed segments
- `recalllayer_mutable_buffer_size` — un-flushed vectors
- `recalllayer_delete_ratio` — tombstone fraction (0..1)
- `recalllayer_storage_bytes` — total segment storage on disk
- `recalllayer_upserts_total`, `recalllayer_deletes_total`, `recalllayer_queries_total`
- `recalllayer_flushes_total`, `recalllayer_auto_flushes_total`
- `recalllayer_query_latency_p50_seconds`, `_p95_seconds`, `_p99_seconds`

### Segment integrity check

To verify that sealed segment files match the checksums recorded in their manifests:

```python
from recalllayer.engine.local_db import LocalVectorDatabase
db = LocalVectorDatabase(collection_id="...", root_dir="...")
errors = db.verify_segment_integrity()
if errors:
    print("Integrity errors:", errors)
```

An empty list means all checksums passed. Segments written before this feature have no
checksum and are silently skipped.

### Deleting a document

```bash
curl -X DELETE http://localhost:8765/v1/documents/{vector_id}
```

The delete writes a tombstone to the WAL and mutable buffer.  The tombstone masks the sealed row immediately in query results.  Compaction physically removes the tombstoned row from sealed segments.

## Volume requirements

`RECALLLAYER_SIDECAR_ROOT_DIR` **must** be on a persistent volume.  Without a durable mount, sealed segments are lost on container restart and RecallLayer returns an empty index.

With the default Docker Compose setup, the `recalllayer_data` named volume satisfies this requirement.

Approximate disk sizing:
- 128-dim float32 vectors: ~2 KB/vector (JSONL with quantization codes)
- 10 000 vectors/segment → ~20 MB/segment
- After compaction: one segment per collection shard

## Known limitations

- **Query latency scales with vector count** — RecallLayer uses Python JSONL segments.  At 100k vectors, warm-cache query latency is ~30–100 ms.  At 1M vectors, plan for 5–30 seconds per query depending on dimensionality.  IVF clustering (`enable_ivf=True`) can reduce this by 3–6×.
- **Single-process only** — no distributed query execution or replication.
- **Not production-hardened** — no rate limiting, no multi-tenancy, no TLS termination (use a reverse proxy for TLS).
- **Experimental** — the storage format and API contract may change between versions.

## Running locally without Docker

```bash
pip install -e ".[postgres]"
export RECALLLAYER_SIDECAR_ROOT_DIR=/tmp/recalllayer
export RECALLLAYER_COLLECTION_ID=myapp
uvicorn recalllayer.api.recalllayer_sidecar_app:app --port 8765
```
