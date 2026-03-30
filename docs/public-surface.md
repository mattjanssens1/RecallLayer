# Public Surface

This file lists the current best surfaces to use when you want the repository to feel coherent quickly.

## Best API to run

```bash
python scripts/run_best_api.py
```

This runs the current best public-facing API entrypoint:

- `src/turboquant_db/api/app_best.py`

Treat other API variants as narrower or more experimental unless a newer doc says otherwise.

## Best local code API

Use:

- `turboquant_db.showcase.ShowcaseScoredDatabase`

## Best benchmark commands

Use these in order:

```bash
python scripts/run_canonical_flow.py
python scripts/export_full_ladder.py
python scripts/export_proof_pack.py
```

Use the proof-pack export when you want one compact, reproducible artifact instead of the broader report bundle.

## Best docs to read next

- `docs/current-surfaces.md`
- `docs/repository-status.md`
- `docs/benchmark-proof-pack.md`
- `docs/legacy-paths.md`

## Why this exists

The repo has multiple runnable surfaces from its evolution. This file is meant to point readers at the current best entrypoints without making them reverse-engineer the history.
