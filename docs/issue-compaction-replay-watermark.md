# Issue: Align compaction with the shard replay watermark contract

## Summary

The repo now has:
- an explicit ordinary flush lifecycle
- a shard replay watermark recorded on flush
- recovery that replays only the post-watermark write-log tail

The next lifecycle seam is compaction.

**Current risk:** compaction rewrites the active sealed set, but the shard replay watermark story is still mostly flush-driven. That creates ambiguity about whether post-compaction recovery is fully aligned with the sealed state actually represented by the replacement segment.

## Why this matters

The repo is now stronger on:
- proof workflow
- canonical paths
- ordinary flush semantics
- basic restart/recovery semantics

That means the next engine-correctness question becomes:

> After compaction replaces one or more active sealed segments, what should the shard replay watermark mean, and how should recovery interpret it?

If this stays vague, the lifecycle story still has a weak edge around:
- post-compaction restart correctness
- sealed ownership after replacement
- confidence in replay-cutoff semantics
- future checkpoint/replay evolution

## Problem statement

Right now:
- flush updates `replay_from_write_epoch`
- recovery replays only writes after that watermark
- compaction rewrites the active segment set

We need one coherent answer to:

> When compaction creates a replacement segment, how should the shard replay watermark be updated so recovery still agrees with the sealed state currently represented in the manifest?

## Goals

- define what the replay watermark means after compaction
- make recovery after compaction agree with pre-restart query visibility
- reduce ambiguity between flush-driven and compaction-driven sealed ownership
- add a small named test set for compaction/recovery interaction

## Non-goals

- do not build a full checkpoint subsystem here
- do not widen scope into WAL truncation or log compaction yet
- do not add new API surfaces

## Questions this issue should answer

1. After compaction succeeds, what should `replay_from_write_epoch` become?
2. Should the replacement segment's `max_write_epoch` define the new boundary?
3. Should the boundary be monotonic even if compaction inputs are surprising?
4. What recovery behavior should hold after compaction with and without new writes?
5. What tests are needed to keep compaction/recovery alignment from regressing?

## Suggested scope

### 1. Document the intended meaning
Write down what shard replay watermark means after:
- ordinary flush
- repeated flushes
- compaction replacement

### 2. Add tests
At minimum:
- recovery after compaction with no new writes
- recovery after compaction + one new write
- shard manifest watermark update after compaction

### 3. Patch compaction executor
On successful compaction:
- update shard replay watermark coherently with the replacement segment

## Acceptance criteria

This issue is done when:
- compaction updates shard replay watermark intentionally
- recovery after compaction is tested
- post-restart visibility after compaction is not in obvious tension with pre-restart visibility
- the repo has a clearer lifecycle story across flush -> compaction -> recovery

## Resolution (2026-04-06)

**Status: CLOSED — resolved.**

All acceptance criteria are met:

- `CompactionExecutor.compact_shard()` updates the shard manifest with `replay_from_write_epoch = max(current_watermark, artifacts.segment_manifest.max_write_epoch)`. This ensures the watermark is monotonic and reflects the epoch range covered by the compacted segment.
- `tests/unit/test_compaction_recovery_lifecycle.py` covers:
  - watermark is aligned and monotonic after compaction
  - watermark does not move backwards when older segments are compacted
  - recovery after compaction with no new writes replays nothing
  - recovery after compaction + new write replays only the newer tail
