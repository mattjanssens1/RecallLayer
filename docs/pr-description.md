## Summary

This stack hardens the repo from “strong prototype” into “proof-ready strong prototype.”

It does two things:

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

## Result

The repo now has:

- a green full test suite from clean state
- clean-state API test isolation
- coherent canonical entrypoints
- a documented proof workflow
- reviewer-facing proof summary docs

## Commits

- `513e35f` — `test(api): harden proof baseline and clean-state isolation`
- `4918ed6` — `docs(proof): consolidate canonical paths and proof workflow`

## Notes

Generated proof artifacts under `reports/` were intentionally left uncommitted in this pass.
