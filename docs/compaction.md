# Compaction

This adds a small local segment compactor for the sealed-segment prototype.

## New module

- `src/turboquant_db/engine/compactor.py`

## What it does

- scans all local sealed segments for a shard
- keeps the latest row for each `vector_id` based on `write_epoch`
- writes one merged sealed segment
- publishes a shard manifest that activates the compacted segment

## Current limits

This first cut is intentionally narrow:

- local file-backed segments only
- latest-write-wins row merge only
- no background scheduling
- no checksum validation yet
- no retired-segment cleanup yet

It is a stepping stone toward the compaction and recovery-hardening milestone.
