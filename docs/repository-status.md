# Repository Status

This repository is an **early but increasingly disciplined retrieval engine prototype**.

The most honest way to understand it today is:

> **RecallLayer is a vector retrieval sidecar for existing databases.**

It already contains meaningful storage-engine and retrieval work. It is not yet a production-ready standalone database platform.

## Real today

The repository already contains real work around:
- write log, mutable buffer, sealed segment runtime, manifest store, and replay path
- exact, compressed, hybrid, reranked, and scored query paths
- local facade and FastAPI surfaces
- benchmark scripts and report exporters
- unit-style and integration-style tests across important paths
- flush lifecycle semantics
- replay watermark recovery semantics
- compaction / retirement / garbage collection lifecycle work
- on-disk per-segment filter indexes (companion `.filter_index.json` written at flush time)
- segment checksum verification (`content_sha256` in manifest, `verify_segment_integrity()`)
- crash-recovery test coverage: WAL replay, watermark correctness, idempotent recovery
- Prometheus-compatible `/metrics` endpoint (segment count, delete ratio, request counters, latency p50/p95/p99)
- auto-flush background task in the HTTP sidecar (`RECALLLAYER_AUTO_FLUSH_INTERVAL_SECONDS`)

## Strongest credible use today

The strongest near-term use case is:
- **Postgres or another host DB remains the source of truth**
- **RecallLayer serves as the vector retrieval sidecar**
- queries return candidate ids and scores
- the application hydrates final records from the host DB

This is a much more credible framing than treating the project as a complete standalone database replacement.

## Measured but still evolving

These areas already exist in meaningful form but are still evolving:
- engine-native inspection and trace reporting
- rerank timing breakdowns
- candidate accounting and query diagnostics
- benchmark presentation and reproducibility polish
- sidecar-oriented API packaging beyond the embedded-library demo path

## Still prototype-level or incomplete

These areas should still be read as prototype or incomplete:
- on-disk posting-list filter indexes (in-memory FilterIndexes and companion filter_index.json exist; no ANN-coupled pre-filter acceleration yet)
- distributed deployment story
- rich production security / tenancy / admin surfaces
- broad claims of algorithmic leadership or full paper fidelity
- large-scale (1M+) workload validation beyond the scale benchmark script

## How to read the repo honestly

The strongest way to evaluate this project today is:

1. read `docs/integration-contract.md`
2. read `docs/postgres-recalllayer-architecture.md`
3. run the canonical flow
4. inspect the benchmark/export outputs
5. trace the hybrid query and lifecycle behavior through the local facade and engine helpers
6. judge it as a retrieval subsystem for an existing stack, not as a finished database platform

## What is trustworthy today

The repo is increasingly trustworthy for:
- exploring compressed retrieval architecture
- exercising hybrid mutable + sealed query behavior
- validating flush / recovery / compaction lifecycle ideas
- benchmarking retrieval behavior and proof workflows
- shaping a sidecar-style retrieval system design

## What still needs work before it feels implementation-ready

To feel less like a prototype and more like an implementable product subsystem, the repo should next improve:
- ANN-coupled pre-filter acceleration using the on-disk filter indexes at query time
- production-scale workload validation (100k+ vectors with realistic update/delete patterns)
- TLS termination and rate limiting (use a reverse proxy for now)
- multi-tenancy / collection-level isolation beyond single collection_id

## Why this file exists

The repository is now strong enough that it benefits from an explicit statement of:
- what is implemented
- what is trustworthy
- what is still experimental
- what product shape the current code most credibly supports