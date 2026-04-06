# Quantizer Experiments

This repository currently includes several quantizer variants for benchmarking and iteration.

## Baseline family

- `ScalarQuantizer`
- `NormalizedScalarQuantizer`
- `ResidualScalarQuantizer`

These variants explore different scalar-coded approximations.

## TurboQuant-like family

- `TurboQuantAdapter`
- `ShiftedTurboQuantAdapter`
- `CenteredTurboQuantAdapter`

These are not the final algorithm, but they provide a structured approximation family for comparison and benchmarking.

## Recommended scripts

### Small comparison

```bash
python scripts/run_quantizer_comparison.py
python scripts/export_quantizer_summary.py
python scripts/export_quantizer_details.py
```

### Clustered comparison

```bash
python scripts/run_cluster_benchmark.py
python scripts/export_cluster_bundle.py
```

### Tradeoff benchmark

```bash
python scripts/run_quantizer_tradeoffs.py
```

This writes:

- `reports/quantizer-tradeoffs.json`
- `reports/quantizer-tradeoffs.md`

It compares exact / compressed / compressed-reranked paths across quantizers and compressed search budgets, so recall / latency / storage tradeoffs are visible in one artifact instead of scattered across separate runs.

## Why this matters

The repository now supports comparing multiple approximation styles on both small and more structured clustered synthetic workloads. This helps the project feel like an evolving retrieval engine rather than a single frozen toy baseline.
