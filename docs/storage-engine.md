# Storage Engine Notes

The engine now has coverage for several failure-oriented paths, not just happy flows.

## Covered durability / recovery themes

- write-ahead durability mode (`DurabilityMode.LOG_SYNC`)
- replay watermark alignment after compaction
- recovery after flush or compaction interruptions
- multi-shard isolation during recovery
- concurrent write-log append / replay consistency checks

## Torture-style test scope

`tests/unit/test_engine_torture.py` is intended to exercise realistic persistence boundary failures:

- concurrent upsert/delete bursts
- crash during shard-manifest save after flush
- crash during shard-manifest update during compaction
- recovery after compaction plus newer tail writes
- recovery preserves tail writes across shards; mutable replay is still collection-scoped before those writes are flushed back into sealed shard segments

This is still a prototype engine, but these tests push it closer to "credible local storage engine" territory instead of a purely happy-path demo.
