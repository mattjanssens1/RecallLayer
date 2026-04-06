# Live Postgres Sidecar Harness

This is the local/dev harness for proving RecallLayer's sidecar story against a **real Postgres database**.

It is intentionally small.
It is meant to prove the integration path, not to claim production-grade Postgres/RecallLayer operations.

## What it covers

The live harness exercises the existing `PsycopgPostgresRepository` path and validates:
- create + sync into RecallLayer
- candidate query + hydration from Postgres
- unpublish/delete behavior
- repair/backfill convergence
- restart/recovery behavior
- compaction preserving expected visibility

## Install

```bash
pip install -e .[dev,postgres]
```

## Required environment variable

```bash
export RECALLLAYER_LIVE_POSTGRES_DSN=postgresql://user:pass@localhost:5432/app
```

## Test entrypoint

```bash
pytest tests/integration/test_recalllayer_sidecar_postgres_live.py -q
```

If the DSN is not set, the live Postgres test module is skipped.

## Expected table shape

The harness creates a temporary `documents_*` table with this shape:

```sql
create table documents (
  id text primary key,
  title text not null,
  body text not null,
  region text not null,
  status text not null default 'published'
);
```

Each test uses an isolated temporary table name and drops it during teardown.

## Why this harness exists

RecallLayer already had an honest Postgres adapter boundary, but the canonical sidecar story was still mostly proven through the in-memory host repository path.

This harness closes that gap for local development by proving that:
- host truth can live in real Postgres
- RecallLayer can still act as the retrieval sidecar
- hydration/repair/restart/compaction behavior stays coherent through the adapter path

## What it does not claim

This harness does **not** claim:
- production HA or failover semantics
- migration tooling
- auth/permissions solved at the sidecar layer
- operational maturity equal to a managed service

It is a local integration confidence layer.
