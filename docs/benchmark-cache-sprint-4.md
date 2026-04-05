# Sprint 4 Cache Summary

Representative subset: `tiny_fixture` and `clustered_fixture`, using the canonical scalar quantizer plus `normalized-scalar` as a scalar control. `TurboQuantAdapter` is intentionally excluded from the canonical table and remains experimental only.

## clustered_fixture_16 / normalized-scalar-int8-127
- `exact-hybrid`: 3.157 ms -> 0.900 ms (-2.257 ms), cache hit rate 0.882, file reads 16 -> 1, decode loads 16 -> 1.
- `compressed-hybrid`: 4.689 ms -> 2.135 ms (-2.554 ms), cache hit rate 0.882, file reads 16 -> 1, decode loads 16 -> 1.
- `compressed-reranked-hybrid`: 5.894 ms -> 2.471 ms (-3.423 ms), cache hit rate 0.920, file reads 24 -> 1, decode loads 24 -> 1.
- With cache enabled, `compressed-reranked-hybrid` vs `exact-hybrid`: 2.471 ms vs 0.900 ms. `compressed-hybrid` stays at 2.135 ms.

## clustered_fixture_16 / scalar-int8-127
- `exact-hybrid`: 2.865 ms -> 0.682 ms (-2.183 ms), cache hit rate 0.882, file reads 16 -> 1, decode loads 16 -> 1.
- `compressed-hybrid`: 3.025 ms -> 1.088 ms (-1.937 ms), cache hit rate 0.882, file reads 16 -> 1, decode loads 16 -> 1.
- `compressed-reranked-hybrid`: 4.228 ms -> 1.313 ms (-2.915 ms), cache hit rate 0.920, file reads 24 -> 1, decode loads 24 -> 1.
- With cache enabled, `compressed-reranked-hybrid` vs `exact-hybrid`: 1.313 ms vs 0.682 ms. `compressed-hybrid` stays at 1.088 ms.

## tiny_fixture / normalized-scalar-int8-127
- `exact-hybrid`: 0.970 ms -> 0.428 ms (-0.542 ms), cache hit rate 0.846, file reads 12 -> 1, decode loads 12 -> 1.
- `compressed-hybrid`: 1.176 ms -> 0.562 ms (-0.614 ms), cache hit rate 0.846, file reads 12 -> 1, decode loads 12 -> 1.
- `compressed-reranked-hybrid`: 1.719 ms -> 0.836 ms (-0.884 ms), cache hit rate 0.895, file reads 18 -> 1, decode loads 18 -> 1.
- With cache enabled, `compressed-reranked-hybrid` vs `exact-hybrid`: 0.836 ms vs 0.428 ms. `compressed-hybrid` stays at 0.562 ms.

## tiny_fixture / scalar-int8-127
- `exact-hybrid`: 0.909 ms -> 0.433 ms (-0.477 ms), cache hit rate 0.846, file reads 12 -> 1, decode loads 12 -> 1.
- `compressed-hybrid`: 0.877 ms -> 0.486 ms (-0.392 ms), cache hit rate 0.846, file reads 12 -> 1, decode loads 12 -> 1.
- `compressed-reranked-hybrid`: 1.293 ms -> 0.661 ms (-0.631 ms), cache hit rate 0.895, file reads 18 -> 1, decode loads 18 -> 1.
- With cache enabled, `compressed-reranked-hybrid` vs `exact-hybrid`: 0.661 ms vs 0.433 ms. `compressed-hybrid` stays at 0.486 ms.

## Status
- Scalar quantizers (`scalar-quantizer`, `normalized-scalar`) remain the only canonical benchmarked quantizers in this report.
- `TurboQuantAdapter` is not geometrically fixed in this sprint. The code stays in the repo for experiments, but canonical scripts and summary tables exclude it.
