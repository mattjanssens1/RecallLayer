# RecallLayer HTTP Sidecar

This is the current lightweight HTTP surface for the **Postgres/host DB truth -> RecallLayer retrieval sidecar** story.

It is intentionally small.
It is useful for local integration, demos, and contract-shaping.
It is **not** presented as a production-ready hosted service yet.

## Run it locally

Install:

```bash
pip install -e .[dev]
```

Start the sidecar service with uvicorn:

```bash
uvicorn turboquant_db.api.recalllayer_sidecar_app:app --host 127.0.0.1 --port 8001 --reload
```

Or without reload:

```bash
uvicorn turboquant_db.api.recalllayer_sidecar_app:app --host 0.0.0.0 --port 8001
```

OpenAPI docs (while running):
- `http://127.0.0.1:8001/docs`
- `http://127.0.0.1:8001/openapi.json`

## Current endpoints

- `GET /healthz`
- `PUT /v1/documents/{document_id}`
- `POST /v1/documents/{document_id}/sync`
- `POST /v1/documents/{document_id}/unpublish`
- `DELETE /v1/documents/{document_id}`
- `POST /v1/query`
- `POST /v1/repair`
- `POST /v1/backfill`
- `POST /v1/flush`
- `POST /v1/compact`

## Quick API examples

### Health

```bash
curl http://127.0.0.1:8001/healthz
```

### Upsert a host document and sync it into RecallLayer

```bash
curl -X PUT http://127.0.0.1:8001/v1/documents/1 \
  -H 'content-type: application/json' \
  -d '{
    "title": "Postgres retrieval guide",
    "body": "How to hydrate ids from a RecallLayer sidecar.",
    "region": "us",
    "status": "published"
  }'
```

### Add another document

```bash
curl -X PUT http://127.0.0.1:8001/v1/documents/2 \
  -H 'content-type: application/json' \
  -d '{
    "title": "Backfill worker notes",
    "body": "Repair and backfill keep the sidecar aligned with host truth.",
    "region": "us"
  }'
```

### Query candidate ids and hydrated rows

```bash
curl -X POST http://127.0.0.1:8001/v1/query \
  -H 'content-type: application/json' \
  -d '{
    "query_text": "postgres sidecar",
    "top_k": 2,
    "region": "us"
  }'
```

Example response shape:

```json
{
  "query": "postgres sidecar",
  "candidate_ids": ["document:1", "document:2"],
  "candidates": [
    {
      "vector_id": "document:1",
      "score": 0.99,
      "metadata": {"region": "us", "status": "published", "source_table": "documents"}
    }
  ],
  "hydrated_results": [
    {
      "document_id": "1",
      "vector_id": "document:1",
      "title": "Postgres retrieval guide",
      "body": "How to hydrate ids from a RecallLayer sidecar.",
      "region": "us",
      "status": "published"
    }
  ]
}
```

### Flush mutable state into a sealed segment

```bash
curl -X POST http://127.0.0.1:8001/v1/flush \
  -H 'content-type: application/json' \
  -d '{"segment_id": "seg-1", "generation": 1}'
```

### Unpublish a document in host truth and mirror that into RecallLayer

```bash
curl -X POST http://127.0.0.1:8001/v1/documents/1/unpublish
```

### Repair known drift for selected ids

```bash
curl -X POST http://127.0.0.1:8001/v1/repair \
  -H 'content-type: application/json' \
  -d '{"document_ids": ["1", "2"]}'
```

### Backfill everything currently present in the host repository

```bash
curl -X POST http://127.0.0.1:8001/v1/backfill
```

### Compact sealed segments

```bash
curl -X POST http://127.0.0.1:8001/v1/compact \
  -H 'content-type: application/json' \
  -d '{
    "output_segment_id": "seg-merged",
    "generation": 2,
    "min_segment_count": 2,
    "max_total_rows": 1000
  }'
```

## Postgres adapter path

The default HTTP app uses an in-memory host repository so the sidecar contract is runnable out of the box.

The repo now also includes an explicit optional Postgres adapter boundary:
- `turboquant_db.sidecar.PsycopgPostgresRepository`

That adapter is intentionally honest:
- it requires `psycopg` to be installed separately
- it assumes a simple `documents` table
- it demonstrates the real adapter path without claiming broader production readiness

Expected table shape:

```sql
create table documents (
  id text primary key,
  title text not null,
  body text not null,
  region text not null,
  status text not null default 'published'
);
```

If you want to instantiate the sidecar with that adapter, do it in Python today:

```python
from turboquant_db.api.recalllayer_sidecar_app import create_recalllayer_sidecar_app
from turboquant_db.sidecar import PsycopgPostgresRepository, RecallLayerSidecar

repo = PsycopgPostgresRepository.from_dsn("postgresql://user:pass@localhost:5432/app")
sidecar = RecallLayerSidecar(host_db=repo, root_dir=".recalllayer_sidecar_http_db")
app = create_recalllayer_sidecar_app(sidecar=sidecar)
```

## Recommended reading next

- `docs/integration-contract.md`
- `docs/postgres-recalllayer-architecture.md`
- `docs/repair-backfill.md`
