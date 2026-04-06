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

### Ground-truth matrix benchmark

```bash
python scripts/run_benchmark_matrix.py
```

This matrix benchmark writes:

- `reports/benchmark-matrix.json`
- `reports/benchmark-matrix.md`

It is intended to compare exact / compressed / compressed-reranked behavior across:

- dataset sizes
- embedding dimensions
- shard counts
- delete ratios
- IVF settings

The benchmark uses per-query mean recall rather than flattened global prefixes, so multi-query Recall@K is measured correctly.

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
- `docs/benchmark-proof-story.md` for the canonical interpretation layer

## Recommended path for contributors

1. Run the quickstart example.
2. Run the showcase benchmark.
3. Run the quantizer comparison.
4. Run the extended benchmark.
5. Inspect `reports/` and compare Markdown + JSON outputs.
