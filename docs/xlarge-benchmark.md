# XLarge Benchmark

The xlarge synthetic benchmark is the current widest synthetic tier in this repository.

## Run it

```bash
python scripts/run_xlarge_benchmark.py
python scripts/export_xlarge_bundle.py
```

## What it is for

Use this tier when you want more stress than the tiny, medium, or clustered synthetic fixtures while still keeping the benchmark lightweight and reproducible.

## What it compares

- scalar-family quantizers
- TurboQuant-like adapter variants
- recall and latency under a wider synthetic workload
