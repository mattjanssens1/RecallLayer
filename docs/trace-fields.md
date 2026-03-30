# Trace Fields

The best current API entrypoint returns an observed-plus trace object.

## Best current API entrypoint

- `src/turboquant_db/api/app_best.py`
- `python scripts/run_best_api.py`

## Key fields

### Request and mode

- `mode`
- `top_k`
- `filters_applied`

### Storage shape

- `mutable_live_count`
- `sealed_segment_count`
- `sealed_segment_ids`

### Result shape

- `result_count`
- `mutable_hit_count`
- `sealed_hit_count`

### Approximation and rerank

- `rerank_candidate_k`
- `candidate_count_estimate`

### Timing

- `latency_ms`

## Why these fields matter

These fields make it easier to understand whether a query is being served mostly from mutable state, sealed segments, or a mix of both, and how much approximate search and reranking work happened along the way.
