# Canonical Path

If you are new to this repository, use this path first.

## Best database facade

Use:

- `turboquant_db.showcase.ShowcaseScoredDatabase`

This is still the clearest local development surface for:

- hybrid queries over mutable and sealed data
- scored hits with metadata
- reranked compressed queries
- benchmark-oriented local runs

## Best API surface

Use:

- `src/turboquant_db/api/app_best.py`
- `python scripts/run_best_api.py`

Treat narrower API variants as experimental unless a newer doc explicitly blesses them.

## Best benchmark entrypoints

Use:

- `python scripts/run_canonical_flow.py`
- `python scripts/export_full_ladder.py`
- `python scripts/export_proof_pack.py`

Use the proof-pack export when you want one compact, reproducible benchmark artifact.

## Best example

Use:

- `python examples/quickstart.py`

## Read these next

- `docs/current-surfaces.md`
- `docs/repository-status.md`
- `docs/benchmark-proof-pack.md`

## Why this file exists

Older modules and docs still exist from the repo's evolution. This file marks the current highest-signal path so contributors and visitors do not have to guess which route is most representative.
