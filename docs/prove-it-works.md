# Prove It Works

This document captures a real proof run for the current repository state.

It is meant to answer a simple question:

> Can this repository demonstrate that it works today from a clean state?

Short answer: **yes, as a strong prototype with honest caveats**.

## Canonical paths

Use these entrypoints for current proof/demo work:

- **Best API:** `src/turboquant_db/api/app_best.py`
- **Run best API:** `python scripts/run_best_api.py`
- **Best local facade:** `turboquant_db.showcase.ShowcaseScoredDatabase`
- **Canonical benchmark workflow:** `python scripts/run_canonical_flow.py`
- **Compact proof artifact:** `python scripts/export_proof_pack.py`

Treat `app_observed.py` and `run_observed_api.py` as compatibility aliases.

## Proof run checkpoint

- **Date:** 2026-03-31
- **Branch:** `pr-23-candidate-restricted-execution`
- **Working state:** local workspace checkout

## What was run

### 1. Full tests

```bash
pytest -q
```

Outcome:

- **104 passed**
- **0 failed**
- **1 deprecation warning** for `app_observed.py` as a soft-deprecated compatibility alias

### 2. Quickstart example

```bash
python examples/quickstart.py
```

Observed output included:

- `exact hybrid: ['doc-1']`
- `compressed hybrid: ['doc-1']`
- `filtered: ['doc-1']`

This demonstrates:

- local upsert/query behavior works
- compressed and exact paths both execute
- metadata filtering works

### 3. Best API demo

```bash
python scripts/demo_best_api_flow.py
```

Observed output included:

- result hits with metadata
- mode: `compressed-reranked-hybrid-observed-plus`
- trace payload with:
  - mutable/sealed hit counts
  - rerank candidate count
  - latency in ms
  - sealed segment ids

This demonstrates:

- the best API path works
- reranked approximate querying works
- trace diagnostics are returned as intended

### 4. Canonical benchmark workflow

```bash
python scripts/run_canonical_flow.py
```

Observed outputs written under `reports/`:

- `reports/showcase_benchmark.md`
- `reports/quantizer_comparison.md`
- `reports/extended_benchmark.md`
- `reports/showcase_bundle.md`
- `reports/showcase_bundle.json`
- `reports/quantizer_bundle.md`
- `reports/quantizer_bundle.json`
- `reports/extended_benchmark_diagnostics.md`
- `reports/extended_benchmark_diagnostics.json`
- `reports/quantizer_comparison_diagnostics.md`
- `reports/quantizer_comparison_diagnostics.json`
- `reports/quantizer_summary.md`
- `reports/quantizer_summary.json`
- `reports/quantizers/scalar-int8-127.json`
- `reports/quantizers/normalized-scalar-int8-127.json`
- `reports/quantizers/turboquant-adapter-127.json`
- `reports/quantizers/shifted-turboquant-adapter-127-s2.json`

This demonstrates:

- the benchmark pipeline completes successfully
- report exporters run end to end
- reproducible artifacts are generated in-repo

### 5. Compact proof artifact

```bash
python scripts/export_proof_pack.py
```

Observed output:

- `reports/proof_pack.md`

## What is real

This proof run supports these claims more comfortably:

- hybrid mutable + sealed query execution is implemented
- exact, compressed, and reranked paths are runnable
- diagnostics-rich API surfaces exist and return meaningful trace data
- benchmark/report artifacts can be generated from the repo
- storage-engine lifecycle work goes beyond toy retrieval and includes compaction/retirement/GC-oriented work

## What still needs careful wording

These claims should still remain careful or qualified:

- full TurboQuant algorithmic fidelity
- production-readiness as a database product
- broad performance authority beyond the benchmark datasets currently included in the repo
- complete consolidation of all legacy/compatibility surface names

## Caveats observed during proof hardening

Before this proof run, the repo needed a small but important cleanup pass:

- stale tests still expected old `observed` mode strings instead of `observed-plus`
- empty-index API tests were polluted by persisted local app state
- app factories needed injectable local roots for clean-state tests
- docs had some remaining drift between `best` and `observed` naming

Those issues were cleaned up enough for the proof run above to complete successfully.

## Practical conclusion

This repository can now be presented honestly as:

- a **strong prototype**
- with a **green test suite**
- a **working best API demo path**
- and a **repeatable benchmark/report proof workflow**

That is materially stronger than "interesting code with plausible claims."
