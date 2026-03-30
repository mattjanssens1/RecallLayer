# Canonical Workflow

This is the shortest path to the current best project experience.

## 1. Read the map

Start with:

- `docs/start-here.md`
- `docs/public-surface.md`
- `docs/observed-api.md`

## 2. Run the best API

```bash
python scripts/run_observed_api.py
```

## 3. Generate the main benchmark/report outputs

```bash
python scripts/run_canonical_flow.py
```

## 4. Inspect reports

Then inspect:

- `reports/showcase_bundle.md`
- `reports/quantizer_bundle.md`
- `reports/extended_benchmark_diagnostics.md`
- `reports/quantizer_summary.md`
- `reports/quantizers/*.json`

## Why this file exists

The repository now has enough working scripts and report exporters that a single canonical workflow is more useful than forcing contributors to infer the order from filenames.
