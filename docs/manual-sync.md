# Manual Sync Guide

A few files are faster to update manually in GitHub than through the connector when the goal is in-place replacement instead of additive iteration.

## Good candidates for manual copy

### README front door

Copy from:

- `docs/readme-refresh.md`

Into:

- `README.md`

### Canonical API alias, if you want to hard-switch older paths

If you decide the older alias should point directly at the current best surface, use content aligned with:

- `src/turboquant_db/api/app_best.py`

Potential manual sync targets:

- `src/turboquant_db/api/app.py`
- `src/turboquant_db/api/app_observed.py`

## Why this file exists

The connector is good at additive improvements, but direct in-place replacements sometimes cost more time and prompts than they are worth. These are the files where a manual copy-paste is often the fastest path.
