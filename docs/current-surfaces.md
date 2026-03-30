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

Treat other API variants as narrower or more experimental unless a newer doc says otherwise.

## Best benchmark flow

Use:

- `python scripts/run_canonical_flow.py`

This is the simplest command when you want the benchmark scripts to run in the intended order.

## Best report export

Use:

- `python scripts/export_full_ladder.py`

This is the broadest export path for the current benchmark ladder.

## Best example

Use:

- `python examples/quickstart.py`

## Why this file exists

Some older docs point at earlier API surfaces from the repo's evolution. This file is meant to be the singular "start here" map until those older docs are tightened.
