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

For the live Postgres harness/adapter path:

```bash
pip install -e .[dev,postgres]
```

### Fastest path: in-memory host repository

```bash
uvicorn recalllayer.api.recalllayer_sidecar_app:app --host 127.0.0.1 --port 8001 --reload
```

### Config-driven startup

The sidecar now supports environment-driven startup.

Common variables:

```bash
export RECALLLAYER_SIDECAR_ROOT_DIR=.recalllayer_sidecar_http_db
export RECALLLAYER_COLLECTION_ID=recalllayer-sidecar-demo
export RECALLLAYER_HOST_REPOSITORY=inmemory   # or postgres
export RECALLLAYER_POSTGRES_DSN=postgresql://user:pass@localhost:5432/app
export RECALLLAYER_POSTGRES_TABLE=documents
export RECALLLAYER_API_KEY=change-me          # optional
```

Then run:

```bash
uvicorn recalllayer.api.recalllayer_sidecar_app:app --host 127.0.0.1 --port 8001 --reload
```

Without reload:

```bash
uvicorn recalllayer.api.recalllayer_sidecar_app:app --host 0.0.0.0 --port 8001
```

OpenAPI docs (while running):
- `http://127.0.0.1:8001/docs`
- `http://127.0.0.1:8001/openapi.json`

## Current endpoints

- `GET /healthz`
- `GET /readyz`
- `GET /v1/status`
- `PUT /v1/documents/{document_id}`
- `POST /v1/documents/{document_id}/sync`
- `POST /v1/documents/{document_id}/unpublish`
- `DELETE /v1/documents/{document_id}`
- `POST /v1/query`
- `POST /v1/repair`
- `POST /v1/backfill`
- `POST /v1/flush`
- `POST /v1/compact`

If `RECALLLAYER_API_KEY` is set, write/query lifecycle endpoints require:

```text
x-api-key: <your-key>
```

Health/readiness remain open so local orchestration stays simple.

## Quick API examples

### Health

```bash
curl http://127.0.0.1:8001/healthz
```

### Status

```bash
curl http://127.0.0.1:8001/v1/status
```

### Upsert a host document and sync it into RecallLayer

```bash
curl -X PUT http://127.0.0.1:8001/v1/documents/1 \
  -H 'content-type: application/json' \
  -H 'x-api-key: change-me' \
  -d '{
    "title": "Postgres retrieval guide",
    "body": "How to hydrate ids from a RecallLayer sidecar.",
    "region": "us",
    "status": "published"
  }'
```

### Query candidate ids and hydrated rows

```bash
curl -X POST http://127.0.0.1:8001/v1/query \
  -H 'content-type: application/json' \
  -H 'x-api-key: change-me' \
  -d '{
    "query_text": "postgres sidecar",
    "top_k": 2,
    "region": "us"
  }'
```

### Flush mutable state into a sealed segment

```bash
curl -X POST http://127.0.0.1:8001/v1/flush \
  -H 'content-type: application/json' \
  -H 'x-api-key: change-me' \
  -d '{"segment_id": "seg-1", "generation": 1}'
```

### Compact sealed segments

```bash
curl -X POST http://127.0.0.1:8001/v1/compact \
  -H 'content-type: application/json' \
  -H 'x-api-key: change-me' \
  -d '{
    "output_segment_id": "seg-merged",
    "generation": 2,
    "min_segment_count": 2,
    "max_total_rows": 1000
  }'
```

## Postgres adapter path

The default HTTP app uses an in-memory host repository so the sidecar contract is runnable out of the box.

The repo also includes an explicit optional Postgres adapter boundary:
- `recalllayer.sidecar.PsycopgPostgresRepository`

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

### Running in Postgres mode

```bash
export RECALLLAYER_HOST_REPOSITORY=postgres
export RECALLLAYER_POSTGRES_DSN=postgresql://user:pass@localhost:5432/app
export RECALLLAYER_POSTGRES_TABLE=documents
uvicorn recalllayer.api.recalllayer_sidecar_app:app --host 127.0.0.1 --port 8001 --reload
```

### Python instantiation path

```python
from recalllayer.api.recalllayer_sidecar_app import create_recalllayer_sidecar_app
from recalllayer.sidecar import PsycopgPostgresRepository, RecallLayerSidecar

repo = PsycopgPostgresRepository.from_dsn("postgresql://user:pass@localhost:5432/app")
repo.ensure_table()
sidecar = RecallLayerSidecar(host_db=repo, root_dir=".recalllayer_sidecar_http_db")
app = create_recalllayer_sidecar_app(sidecar=sidecar)
```

### Local/dev live harness

```bash
pip install -e .[dev,postgres]
docker run --rm --name recalllayer-postgres -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=recalllayer -p 5432:5432 postgres:16-alpine
export RECALLLAYER_POSTGRES_DSN=postgresql://postgres:postgres@127.0.0.1:5432/recalllayer
python examples/postgres_sidecar_live.py
pytest tests/integration/test_recalllayer_sidecar_postgres_live.py -q
```

If you prefer the test to launch its own disposable container, use:

```bash
pip install -e .[dev,postgres]
RECALLLAYER_RUN_LIVE_POSTGRES_TESTS=1 pytest tests/integration/test_recalllayer_sidecar_postgres_live.py -q
```

## Current limits

This is still a small service surface.
It now has a better startup/config story and a minimal optional auth guard, but it is still not claiming:
- full production hardening
- deep operational observability
- broad multi-tenant auth/authorization guarantees
- managed deployment tooling

Treat it as a practical local/dev sidecar service, not a finished hosted product.

## Recommended reading next

- `docs/integration-contract.md`
- `docs/postgres-recalllayer-architecture.md`
- `docs/postgres-live-harness.md`
- `docs/repair-backfill.md`
