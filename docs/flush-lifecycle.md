# Flush Lifecycle (current engine contract)

## Status

This note defines the **intended current-engine flush contract** for the local storage prototype.

It is deliberately narrower than a full production durability design.
In particular, the current write-log recovery path should still be treated as prototype replay behavior, not as a checkpoint-aware recovery barrier.

## Why this exists

The repository already has a stronger compaction / retirement / GC story than its ordinary flush path.
This document makes the ordinary flush path explicit so future engine work has a stable target.

## Scope

This note describes:
- runtime flush behavior
- manifest-visible expectations
- query-visible expectations
- empty flush and repeated flush behavior

This note does **not** claim that flush is already a full durability checkpoint mechanism.

## Current intended model

The current engine should treat ordinary flush as an **additive sealed flush with mutable drain**.

That means:
1. take the current live mutable snapshot
2. write one sealed segment from that snapshot
3. add that segment to the shard manifest active set
4. keep previously active sealed segments active unless a later lifecycle operation replaces or retires them
5. clear the flushed mutable entries from runtime mutable state

This keeps ordinary flush semantics compatible with the existing multi-segment engine shape while still giving runtime state a clean mutable → sealed transition.

## Flush preconditions

### Non-empty flush

A non-empty flush is valid when the mutable buffer contains at least one live entry for the target shard.

### Empty flush

An empty flush should be treated as a **no-op**.

An empty flush should not:
- create a zero-row active segment
- advance active sealed state
- create misleading manifest changes

## Flush postconditions

After a successful non-empty flush:

1. exactly one new segment has been built for the flush target
2. that segment is query-visible through the shard manifest
3. the segment manifest has coherent lifecycle metadata
4. runtime mutable state no longer exposes the entries that were just flushed
5. new writes after the flush are visible through mutable state until the next flush

## Manifest expectations

For the current additive flush model:
- the shard manifest active set should include the new flushed segment
- previously active sealed segments should remain active after ordinary flush
- compaction / retirement may later replace or retire older active segments
- manifest-visible sealed state should match the sealed state searched by normal queries

## Lifecycle metadata expectations

A flushed segment should carry:
- a segment id
- a generation that advances deterministically
- `sealed_at`
- `activated_at`
- `min_write_epoch`
- `max_write_epoch`
- row counters that are internally consistent

## Query visibility expectations

Immediately after a successful flush:
- previously flushed rows should be query-visible from sealed state
- those same rows should no longer rely on mutable visibility to remain queryable
- new writes after the flush should appear via mutable state until the next flush

## Repeated flush behavior

Under the current intended contract, repeated flushes are deterministic:

- first non-empty flush => active sealed segment set includes A
- second non-empty flush after more writes => active sealed segment set includes A + B
- ordinary queries consult the active sealed set plus any newer mutable writes

Repeated ordinary flushes are therefore **additive across the active sealed set** until a later compaction / retirement step rewrites that set.

## Recovery note

Current recovery still replays the write log into mutable state and should be read as prototype durability behavior.

That means:
- flush improves runtime lifecycle clarity
- flush does not yet imply a checkpointed replay cutoff

A future issue can align recovery semantics with flush semantics more fully.

## Tests this contract wants to keep green

A small named lifecycle cluster should cover at least:
- empty flush is a no-op
- flush creates active sealed segment with lifecycle metadata
- flush clears flushed mutable entries
- flush followed by new writes leaves only new writes mutable
- repeated flushes have deterministic additive active-segment behavior
- post-flush query visibility matches manifest-visible sealed state
