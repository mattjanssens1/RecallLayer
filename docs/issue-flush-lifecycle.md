# Issue: Align recovery semantics with the flush lifecycle contract

## Summary

The repo now has a clearer and tested ordinary flush lifecycle:
- empty flush is a no-op
- successful flush drains flushed mutable rows
- repeated flushes add new sealed segments to the active set
- ordinary query visibility across flushes is now much more explicit

The next asymmetry is recovery.

**Current risk:** runtime flush semantics are now clearer than recovery semantics. Recovery still replays the full write log back into mutable state, which can reintroduce ambiguity about what should be visible from mutable versus sealed state after restart.

This issue is about making recovery semantics consistent with the flush lifecycle contract without pretending the repo needs a giant production durability redesign all at once.

## Why this matters

The repo now has a stronger story for:
- proof workflow
- canonical paths
- compaction / retirement / GC
- ordinary flush lifecycle behavior

That means the next highest-leverage engine question becomes:

> After restart, how should the engine reconstruct sealed state, mutable state, and their visibility boundary in a way that agrees with the flush contract?

If recovery remains fuzzy, then all of these remain weaker than they should be:
- restart correctness
- post-recovery query visibility
- trust in sealed-vs-mutable boundaries
- future checkpointing or replay-cutoff work
- confidence in the storage-engine lifecycle as a whole

## Problem statement

Right now:
- runtime flush drains mutable entries after they are sealed
- active sealed state is manifest-driven
- recovery still replays the entire write log into mutable state

That means runtime and restart behavior can tell different stories about where the latest visible rows live.

We need one coherent answer to:

> What should recovery rebuild into mutable state, what should remain represented only by sealed state, and what role should flush play in defining that boundary?

## Goals

- define recovery semantics that agree with the current flush contract
- reduce ambiguity between runtime state and post-restart state
- make sealed-vs-mutable visibility boundaries more trustworthy after recovery
- establish whether the repo wants a true checkpoint boundary, a replay watermark, or a narrower intermediate model
- add a small named set of recovery/lifecycle tests future engine work must keep green

## Non-goals

- do not turn this into a full production WAL/checkpoint subsystem unless a real blocker appears
- do not widen scope into broad distributed durability design
- do not add new API product surfaces here
- do not revisit benchmark/report expansion in this issue

## Questions this issue should answer

1. After a flush, what state should recovery rebuild into mutable memory?
2. Should flushed rows be replayed back into mutable after restart, or should recovery respect a flush/replay boundary?
3. What metadata is needed to define that boundary cleanly?
4. Should the boundary be manifest-based, log-watermark-based, checkpoint-file-based, or some simpler hybrid?
5. How should post-recovery query visibility compare to pre-restart query visibility?
6. How should repeated flushes interact with replay cutoff rules?
7. Which parts of this are durable engine invariants vs temporary prototype simplifications?

## Suggested scope

### 1. Write down the intended recovery model
Document, in code-facing terms:
- what recovery loads from manifests / sealed segments
- what recovery rebuilds into mutable state
- what replay range is allowed after one or more flushes
- what guarantees should hold before and after restart

### 2. Audit current implementation
Inspect:
- `RecoveryManager`
- write-log replay assumptions
- shard / segment manifest data available at recovery time
- whether any flush metadata needed for replay cutoff is currently missing

### 3. Decide the smallest coherent fix
Likely options:
- replay watermark recorded at flush time
- manifest-linked replay boundary
- explicit checkpoint metadata file
- temporary "good enough" rule that narrows ambiguity without full checkpointing

### 4. Add tests
At minimum, cover:
- restart after one flush
- restart after repeated flushes
- restart after flush + new writes
- query correctness before vs after restart
- no obvious re-shadowing of sealed rows by replayed mutable state unless intentional

## Likely failure modes to guard against

- restart repopulates mutable with rows that should remain sealed-only
- post-restart queries diverge from pre-restart queries in surprising ways
- replay cutoff metadata is missing, inconsistent, or ignored
- repeated flushes make recovery state ambiguous
- tests pass only because persisted local state leaks between runs

## Acceptance criteria

This issue is done when:

- recovery semantics are explicit in docs and/or code comments
- restart behavior is meaningfully aligned with the flush lifecycle contract
- recovery after one or more flushes is tested
- post-restart query visibility is not in obvious tension with pre-restart visibility
- the repo has a clearer story for what recovery means in the current engine
- the work produces a small, named set of recovery/lifecycle tests that future storage changes must keep green

## Nice-to-have

- one concise lifecycle diagram or note connecting write log -> mutable -> flush -> sealed -> recovery
- explicit statement of what is still prototype-level after this pass

## Deliverable mindset

The deliverable is not “more replay code.”
The deliverable is:

> a recovery story that agrees with the flush story

## Suggested labels

- `engine`
- `storage-lifecycle`
- `recovery`
- `correctness`
- `tests`
