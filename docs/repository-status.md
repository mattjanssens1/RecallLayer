# Repository Status

This repository is an **early vector-database prototype**.

It already contains meaningful engine work, runnable examples, API surfaces, and benchmark/export scripts. It is not yet a production-ready database, and some of its quantization and positioning language should be read in that light.

## Real today

- write log, mutable buffer, sealed segment runtime, manifest store, and replay path
- exact, compressed, hybrid, reranked, and scored query paths
- local facade and FastAPI surfaces
- benchmark scripts and report exporters
- unit-style and integration-style tests across important paths

## Measured but evolving

- engine-native inspection and trace reporting
- rerank timing breakdowns
- candidate accounting and query diagnostics
- benchmark presentation and reproducibility polish

## Experimental or placeholder

- TurboQuant adapter fidelity relative to the paper or any production-quality implementation
- larger and more realistic benchmark datasets
- deeper planning, indexing, and background lifecycle work

## How to read the repo honestly

The strongest way to evaluate this project is:

1. run the canonical flow
2. inspect the benchmark/export outputs
3. trace the hybrid query path from local facade to engine helpers
4. treat TurboQuant wording as prototype-oriented unless backed by measured results in the repo

## Why this file exists

The repo is strong enough that it benefits from a direct statement of what is implemented versus what is still experimental.
