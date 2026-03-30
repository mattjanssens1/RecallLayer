# Benchmark Guide

This repository has a few benchmark entrypoints. Use these in order.

## Canonical benchmark scripts

### Small showcase benchmark

```bash
python scripts/run_showcase_benchmark.py
python scripts/export_showcase_bundle.py
```

### Quantizer comparison

```bash
python scripts/run_quantizer_comparison.py
python scripts/export_benchmark_diagnostics.py
```

### Medium synthetic benchmark

```bash
python scripts/run_extended_benchmark.py
python scripts/export_extended_diagnostics.py
```

## Report outputs

The scripts write Markdown and JSON artifacts under `reports/`.

Common outputs include:

- comparison tables in Markdown
- diagnostics metadata in JSON
- bundle-style reports for the showcase path

## What to look at first

- recall differences between quantizers
- latency differences between exact and compressed paths
- traced API diagnostics for query behavior

## Recommended path for contributors

1. Run the quickstart example.
2. Run the showcase benchmark.
3. Run the quantizer comparison.
4. Run the extended benchmark.
5. Inspect `reports/` and compare Markdown + JSON outputs.
