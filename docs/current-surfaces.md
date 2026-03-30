# Current Surfaces

If you want the shortest path through this repository, start here.

## Best local facade

Use:

- `turboquant_db.showcase.ShowcaseScoredDatabase`

This is the clearest local development surface for:

- hybrid queries over mutable and sealed data
- scored hits with metadata
- compressed plus reranked query behavior
- benchmark-oriented local runs

## Best API entrypoint

Use:

- `src/turboquant_db/api/app_best.py`
- `python scripts/run_best_api.py`

Use `app_observed.py` and `run_observed_api.py` only as soft-deprecated compatibility aliases for older notes and scripts.

Use `app_inspected.py` and `app_measured.py` when you explicitly want narrower experimental inspection surfaces.

## Best benchmark flow

Use:

- `python scripts/run_canonical_flow.py`

This is the simplest command when you want the benchmark scripts to run in the intended order.

## Best report export

Use:

- `python scripts/export_full_ladder.py`

This is the broadest export path for the current benchmark ladder.

## Best compact proof artifact

Use:

- `python scripts/export_proof_pack.py`

Use this when you want one small, reproducible benchmark artifact.

## Best example

Use:

- `python examples/quickstart.py`

## Read these next

- `docs/api-surface-policy.md`
- `docs/deprecations.md`
- `docs/repository-status.md`
- `docs/benchmark-proof-pack.md`

## Why this file exists

Some older docs and surface names still exist from the repo's evolution. This file is meant to be the singular "start here" map until a future consolidation pass removes more aliases.
