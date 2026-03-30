# Deprecations

This file tracks **soft deprecations** for public-facing names in the repository.

## Soft-deprecated compatibility aliases

These names still work, but new docs, examples, and commands should prefer the canonical replacements.

### API module alias

Prefer:

- `src/turboquant_db/api/app_best.py`

Instead of:

- `src/turboquant_db/api/app_observed.py`

### Runner alias

Prefer:

- `python scripts/run_best_api.py`

Instead of:

- `python scripts/run_observed_api.py`

## Experimental but not deprecated

These surfaces are still valid for targeted engine work, but they are not the default public path:

- `src/turboquant_db/api/app_inspected.py`
- `src/turboquant_db/api/app_measured.py`

## Removal policy

There is no forced removal date yet. These aliases remain available so older notes and commands keep working while the repo continues to consolidate around fewer stronger surfaces.
