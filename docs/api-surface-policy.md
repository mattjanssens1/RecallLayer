# API Surface Policy

This repository currently keeps multiple API entrypoints for compatibility and experimentation.

## Canonical public entrypoint

Use:

- `src/turboquant_db/api/app_best.py`
- `python scripts/run_best_api.py`

This is the default public-facing API path for new usage.

## Compatibility alias (soft-deprecated)

Use only when older notes or scripts already point at it:

- `src/turboquant_db/api/app_observed.py`
- `python scripts/run_observed_api.py`

These names intentionally resolve to the same surface as `app_best.py`. They remain available during a soft-deprecation window, but new docs, examples, and commands should use the canonical `best` names instead.

## Experimental inspection surfaces

Use when you specifically want richer or more specialized diagnostics:

- `src/turboquant_db/api/app_inspected.py`
- `src/turboquant_db/api/app_measured.py`

These are useful during engine development, but they are not the default public entrypoint and may change faster than the canonical surface.

## Internal server modules

Files named `showcase_server_*` are implementation modules behind the higher-level `app_*` entrypoints. They are real code, but they should be treated as lower-level surfaces when deciding what to link in docs.

## Why this file exists

The repo has grown a few surface names as the prototype evolved. This file is here to make the intended hierarchy explicit until a future consolidation pass removes or retires more aliases.
