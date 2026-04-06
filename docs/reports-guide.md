# Reports Guide

Most benchmark and diagnostics scripts in this repository write artifacts under `reports/`.

## Common report files

### Showcase bundle

- `showcase_bundle.md`
- `showcase_bundle.json`

### Quantizer bundle

- `quantizer_bundle.md`
- `quantizer_bundle.json`

### Quantizer summary

- `quantizer_summary.md`
- `quantizer_summary.json`
- `reports/quantizers/*.json`

### Extended benchmark

- `extended_benchmark_diagnostics.md`
- `extended_benchmark_diagnostics.json`

## One-shot export

To generate the main bundle of report artifacts, run:

```bash
python scripts/export_all_reports.py
```

## Why this matters

A repository with multiple benchmark scripts becomes much easier to trust when the output directory has a clear mental model.

If you want the current narrative interpretation of the main benchmark outputs, read:
- `docs/benchmark-proof-story.md`
- `docs/benchmark-proof-pack.md`
