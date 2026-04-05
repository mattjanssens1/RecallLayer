# Issue: Enforce tombstone masking across mutable and sealed hybrid query paths

## Summary

Review on PR #26 surfaced a real correctness gap:
- deletes can be replayed into mutable state after restart
- but hybrid query currently does not use mutable tombstones to mask matching sealed rows

That means deleted rows can still reappear from sealed segments even when mutable state knows they are deleted.

## Why this matters

The repo now has stronger lifecycle pieces for:
- ordinary flush
- replay watermark recovery
- compaction / replay-boundary alignment

But delete visibility is still weaker than upsert visibility.

If hybrid tombstone masking is not enforced, then all of these become less trustworthy:
- delete correctness after restart
- delete correctness after flush/compaction
- latest-visible-row semantics across mutable + sealed state
- confidence in the storage lifecycle story as a whole

## Problem statement

We need one coherent answer to:

> If mutable state contains a tombstone for `vector_id = X`, should sealed rows for `X` still be eligible for query results?

The current answer is effectively "yes, sometimes," which is wrong for a latest-write-wins model.

## Goals

- ensure mutable tombstones mask matching sealed rows during hybrid query execution
- ensure delete visibility remains correct before and after restart
- make hybrid query semantics more consistent with write-log / recovery semantics
- add a focused test set for delete visibility across mutable + sealed state

## Non-goals

- do not build full physical delete compaction here
- do not widen scope into WAL truncation or production durability design
- do not add new API surfaces

## Suggested scope

### 1. Define the masking rule
Document the current-engine expectation:
- if mutable contains a tombstone for a vector id, sealed rows for that id are not query-visible

### 2. Patch hybrid query path
Audit and update the sealed candidate path / merge path so mutable tombstones actually mask sealed hits.

### 3. Add tests
At minimum:
- delete after flush masks sealed row before restart
- delete after flush masks sealed row after restart
- delete + new upsert of same vector id follows latest-write-wins behavior
- masking still behaves correctly after compaction

## Acceptance criteria

This issue is done when:
- mutable tombstones mask matching sealed rows during hybrid query
- delete visibility before and after restart is covered by tests
- the repo has a clearer story for delete semantics across mutable + sealed state
