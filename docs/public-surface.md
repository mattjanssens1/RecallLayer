# Public Surface

This file lists the current best surfaces to use when you want the repository to feel coherent quickly.

## Best API to run

```bash
python scripts/run_observed_api.py
```

This runs the current best public-facing API:

- `src/turboquant_db/api/app_observed.py`

## Best local code API

Use:

- `turboquant_db.showcase.ShowcaseScoredDatabase`

## Best benchmark scripts

Use these in order:

```bash
python scripts/run_showcase_benchmark.py
python scripts/run_quantizer_comparison.py
python scripts/run_extended_benchmark.py
python scripts/export_showcase_bundle.py
python scripts/export_quantizer_bundle.py
python scripts/export_extended_diagnostics.py
```

## Best docs to read next

- `docs/start-here.md`
- `docs/canonical-path.md`
- `docs/benchmark-guide.md`
- `docs/legacy-paths.md`

## Why this exists

The repo now has enough working surfaces that a concise map is more useful than another architecture essay.
