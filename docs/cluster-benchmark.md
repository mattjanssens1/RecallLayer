# Cluster Benchmark

The clustered benchmark is the current best synthetic workload for checking whether approximate retrieval preserves neighborhood structure better than the tiny fixture alone.

## Run it

```bash
python scripts/run_cluster_benchmark.py
python scripts/export_cluster_bundle.py
```

## What it covers

- several quantizer families
- clustered synthetic embeddings
- recall and latency comparison across approximation styles

## Why use it

This benchmark sits between the tiny fixture and a future larger-scale benchmark suite. It is a good next step when you want to compare quantizer variants on something that has clearer cluster structure.
