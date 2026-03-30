# Repository Layout

## 1. Goal

Organize the repository so implementation can start without a naming war every third commit.

The layout should support:

- engine development
- benchmark harnesses
- experiments
- service APIs
- future clients and tooling

## 2. Proposed top-level layout

```text
TurboQuant-native-vector-database/
  README.md
  pyproject.toml
  docs/
  src/
  benchmarks/
  tests/
  scripts/
  configs/
```

## 3. Docs

```text
docs/
  architecture.md
  roadmap.md
  benchmark-plan.md
  data-model.md
  storage-engine.md
  api.md
  repository-layout.md
  implementation-plan.md
```

Purpose:

- architecture and design references
- implementation sequencing
- benchmark rules and reporting expectations

## 4. Source layout

Use a single top-level Python package initially.

```text
src/
  turboquant_db/
    __init__.py
    config/
    model/
    engine/
    quantization/
    retrieval/
    filters/
    rerank/
    api/
    benchmark/
    storage/
    telemetry/
    utils/
```

## 5. Package breakdown

### 5.1 `config/`

Configuration models and loaders.

Suggested files:

```text
config/
  collections.py
  engine.py
  benchmark.py
```

### 5.2 `model/`

Stable domain objects.

Suggested files:

```text
model/
  collection.py
  records.py
  segment.py
  manifest.py
  trace.py
```

These should mirror the entities in `docs/data-model.md`.

### 5.3 `engine/`

Core storage-engine behavior.

Suggested files:

```text
engine/
  write_log.py
  mutable_buffer.py
  segment_builder.py
  segment_reader.py
  manifest_store.py
  query_executor.py
  compactor.py
  recovery.py
```

### 5.4 `quantization/`

Compression abstractions and implementations.

Suggested files:

```text
quantization/
  base.py
  scalar.py
  binary.py
  turboquant_like.py
  transforms.py
```

The initial `turboquant_like.py` can be a placeholder interface until the exact implementation path is decided.

### 5.5 `retrieval/`

Candidate-generation backends.

Suggested files:

```text
retrieval/
  base.py
  scan.py
  ivf.py
  graph.py
  planner.py
```

Recommendation:

- implement `scan.py` first
- keep `ivf.py` and `graph.py` as later modules

### 5.6 `filters/`

Exact metadata filtering.

Suggested files:

```text
filters/
  base.py
  bitmap.py
  posting.py
  range_index.py
  evaluator.py
```

### 5.7 `rerank/`

Higher-precision reranking.

Suggested files:

```text
rerank/
  base.py
  fetch.py
  scoring.py
```

### 5.8 `api/`

HTTP service and schemas.

Suggested files:

```text
api/
  server.py
  schemas.py
  routes/
    collections.py
    vectors.py
    query.py
    traces.py
    maintenance.py
```

### 5.9 `benchmark/`

Benchmark runner support code.

Suggested files:

```text
benchmark/
  datasets.py
  runner.py
  metrics.py
  report.py
  truthset.py
```

### 5.10 `storage/`

Low-level filesystem or object-store interactions.

Suggested files:

```text
storage/
  files.py
  manifests.py
  segments.py
  checksums.py
```

### 5.11 `telemetry/`

Metrics, traces, and timing helpers.

Suggested files:

```text
telemetry/
  counters.py
  timing.py
  tracing.py
```

## 6. Benchmarks layout

```text
benchmarks/
  datasets/
  configs/
  runners/
  reports/
  fixtures/
```

### Notes

- `datasets/` contains adapters, not giant raw corpora
- `configs/` contains reproducible run definitions
- `reports/` stores generated summaries and plots later

## 7. Tests layout

```text
tests/
  unit/
  integration/
  benchmark_smoke/
```

### Unit tests
Focus on:

- config validation
- segment encoding and decoding
- filter correctness
- quantization interfaces
- manifest logic

### Integration tests
Focus on:

- write then query flows
- flush and compaction behavior
- recovery from log replay
- delete visibility

### Benchmark smoke tests
Focus on:

- harness execution
- result file generation
- small local datasets

## 8. Scripts layout

```text
scripts/
  run_benchmark.py
  create_collection.py
  load_fixture_data.py
  compact_collection.py
```

Use scripts for repeatable developer workflows, not as the place where core logic goes to hide.

## 9. Configs layout

```text
configs/
  collections/
  benchmarks/
  engine/
```

Examples:

- `configs/collections/documents.yaml`
- `configs/benchmarks/local_small.yaml`
- `configs/engine/default.yaml`

## 10. Coding conventions

### Package boundaries

- `model/` should stay dependency-light
- `engine/` should depend on `model/`, `storage/`, `quantization/`, `filters/`, `retrieval/`, `rerank/`
- `api/` should depend on engine-facing service objects, not raw file layout details

### Rule of thumb

If an API route starts importing segment-footers directly, the architecture has started chewing on its own shoelaces.

## 11. First real files to implement

In order:

1. `model/collection.py`
2. `model/records.py`
3. `model/manifest.py`
4. `engine/write_log.py`
5. `engine/mutable_buffer.py`
6. `quantization/base.py`
7. `retrieval/base.py`
8. `retrieval/scan.py`
9. `rerank/scoring.py`
10. `benchmark/runner.py`

## 12. Summary

This layout is designed to support a real build:

- domain models are explicit
- storage engine parts are separated
- retrieval and quantization remain pluggable
- benchmarks are first-class citizens
- tests have a home from day one

That gives the repository enough structure to grow without becoming a cable drawer full of one-off experiments.
