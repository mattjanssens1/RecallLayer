## Summary

This stack hardens the repo from “strong prototype” into “proof-ready strong prototype,” then follows through on the next engine-correctness seam: flush lifecycle invariants.

It now does three things:

1. **Restores test trust**
   - fixes stale observed-mode expectations
   - adds clean-state isolation for empty-index API tests
   - relaxes one brittle entrypoint test that depended on exact wrapper identity
   - adds a focused `.gitignore` so proof runs stop polluting `git status`

2. **Consolidates the proof story**
   - makes `best` the named canonical path
   - keeps `observed` explicitly compatibility-only
   - adds a proof doc stack:
     - `docs/proof-checklist.md`
     - `docs/prove-it-works.md`
     - `docs/reviewer-summary.md`
     - `docs/proof-status-snippet.md`

3. **Defines and enforces flush lifecycle invariants**
   - adds `docs/flush-lifecycle.md` to make the ordinary flush contract explicit
   - makes empty flush a no-op instead of creating misleading zero-row active state
   - stamps `sealed_at` and `activated_at` on flushed segments
   - drains flushed mutable entries after successful flush
   - preserves query visibility across repeated flushes by adding new flushed segments to the active sealed set
   - adds focused flush lifecycle tests
   - hardens traced API integration coverage with isolated temp storage

## Result

The repo now has:

- a green full test suite from clean state
- clean-state API test isolation
- coherent canonical entrypoints
- a documented proof workflow
- a clearer and tested ordinary flush lifecycle contract
- better alignment between manifest-visible sealed state and query-visible sealed state

## Commits

- `513e35f` — `test(api): harden proof baseline and clean-state isolation`
- `78a5db6` — `docs(proof): consolidate canonical paths and proof workflow`
- `[new commit]` — `feat(engine): define and enforce flush lifecycle invariants`

## Flush lifecycle contract (current engine)

Ordinary flush now behaves as:

- non-empty mutable snapshot -> one new sealed segment
- new segment added to the active sealed set
- flushed mutable rows removed from runtime mutable state
- repeated flushes preserve sealed query visibility until a later compaction / retirement step rewrites the active set
- empty flush -> no-op

This intentionally improves runtime lifecycle clarity without claiming that flush is already a full checkpoint-aware recovery barrier.

## Validation

```bash
/home/moose/.openclaw/workspace/TurboQuant-native-vector-database/.venv/bin/python -m pytest tests/unit tests/integration -q
```

Result:
- `111 passed`
- `1 warning` (`app_observed.py` soft deprecation warning)

## Notes

- Generated proof artifacts under `reports/` were intentionally left uncommitted in the earlier proof pass.
- `docs/issue-flush-lifecycle.md` is planning context; `docs/flush-lifecycle.md` is the durable contract doc for this implementation pass.
