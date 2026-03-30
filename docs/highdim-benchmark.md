# HighDim Benchmark

The high-dimensional benchmark is the current best synthetic tier for checking how the approximation families behave when vectors have more realistic dimensionality than the earlier 2D-style fixtures.

## Run it

```bash
python scripts/run_highdim_benchmark.py
python scripts/export_highdim_bundle.py
```

## What it is for

Use this tier when you want to compare quantizer variants under a wider synthetic vector shape without jumping to a fully external dataset.

## What it compares

- scalar-family quantizers
- TurboQuant-like adapter variants
- recall and latency under higher-dimensional synthetic inputs
