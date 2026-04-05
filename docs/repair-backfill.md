# RecallLayer Repair and Backfill

This document makes the repair/backfill story explicit for the canonical **Postgres + RecallLayer** sidecar model.

## Why this exists

RecallLayer is intentionally not the source of truth.
If the host DB and RecallLayer drift apart:
- the **host DB wins**
- hydration should drop stale ids safely
- repair/backfill should restore RecallLayer from host truth

That safety net is part of the intended product shape, not an optional footnote.

## When to use repair

Use repair when you believe RecallLayer is mostly correct, but some ids may be stale.

Examples:
- a sync worker crashed after the host transaction committed
- a deploy temporarily disabled sidecar writes
- a subset of documents was re-embedded or unpublished
- hydration is dropping candidate ids that no longer exist in Postgres

Current local surface:
- library: `RecallLayerSidecar.repair_documents(document_ids)`
- HTTP: `POST /v1/repair`

Example:

```bash
curl -X POST http://127.0.0.1:8001/v1/repair \
  -H 'content-type: application/json' \
  -d '{"document_ids": ["1", "2", "3"]}'
```

What it does today:
- reads host truth for each requested id
- upserts published rows into RecallLayer
- issues sidecar deletes for missing or unpublished rows

## When to use backfill

Use backfill when RecallLayer needs to be rebuilt or filled from the host DB at larger scope.

Examples:
- first-time sidecar adoption
- full reindex after embedding version change
- restore after sidecar storage loss
- migration into a fresh RecallLayer deployment

Current local surface:
- library: `RecallLayerSidecar.backfill_from_host()`
- HTTP: `POST /v1/backfill`

Example:

```bash
curl -X POST http://127.0.0.1:8001/v1/backfill
```

What it does today:
- lists all known host document ids
- syncs each one into RecallLayer

## Recommended production-shaped flow

The intended sync ladder is:

1. **Inline or outbox-driven sync** handles normal writes
2. **Repair** fixes targeted drift
3. **Backfill** rebuilds larger scopes when needed

That yields this honest model:

```text
Postgres truth
   -> inline write or outbox event
   -> RecallLayer sync
   -> query/hydration
   -> repair/backfill if drift appears
```

## Outbox tie-in

This repo now includes a lightweight event-sync shape in:
- `src/turboquant_db/sidecar_sync.py`
- `tests/unit/test_sidecar_sync.py`

That module demonstrates the recommended path:
- host write updates the source row first
- an outbox event is recorded
- a worker consumes the event
- the worker calls `sidecar.sync_document(...)`
- repair/backfill remain the catch-up path

## What is real today vs still pending

Real in this repo today:
- hydration drops stale ids safely
- explicit repair path
- explicit backfill path
- HTTP endpoints for repair/backfill
- a lightweight outbox/worker model that makes the event-driven story concrete

Still not claimed:
- durable production outbox storage
- exactly-once delivery
- transactional coupling between Postgres and RecallLayer
- parallelized bulk backfill machinery
- full observability/metrics for repair jobs

## Suggested operating rule

If host truth and RecallLayer disagree, do **not** try to make RecallLayer authoritative.
Repair RecallLayer from the host DB instead.
