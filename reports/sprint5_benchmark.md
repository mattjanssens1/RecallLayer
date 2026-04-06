# Sprint 5 Benchmark — Compressed vs Exact at Scale

Fixture: `medium_fixture_5000x128` (5 000 vectors, 128-dim, cache enabled).

| Fixture | Quantizer | IVF | Query path | Latency ms | Mutable ms | Sealed ms | Rerank ms | Recall@10 | Candidates |
|---|---|---|---|---:|---:|---:|---:|---:|---:|
| medium_fixture_5000x128 | scalar-int8-127 | ivf-disabled | exact-hybrid | 281.678 | 0.045 | 276.461 | 0.000 | 1.000 | 10.0 |
| medium_fixture_5000x128 | scalar-int8-127 | ivf-disabled | compressed-hybrid | 176.888 | 0.029 | 159.963 | 0.000 | 1.000 | 10.0 |
| medium_fixture_5000x128 | scalar-int8-127 | ivf-disabled | compressed-reranked-hybrid | 163.142 | 0.027 | 143.677 | 11.025 | 1.000 | 40.0 |
| medium_fixture_5000x128 | scalar-int8-127 | ivf-enabled | exact-hybrid | 288.611 | 0.044 | 282.275 | 0.000 | 1.000 | 10.0 |
| medium_fixture_5000x128 | scalar-int8-127 | ivf-enabled | compressed-hybrid | 47.380 | 0.024 | 35.419 | 0.000 | 1.000 | 10.0 |
| medium_fixture_5000x128 | scalar-int8-127 | ivf-enabled | compressed-reranked-hybrid | 49.785 | 0.024 | 34.832 | 10.620 | 1.000 | 40.0 |

---

# Sprint 5 Summary

## ivf-disabled
- `compressed-hybrid` vs `exact-hybrid`: 176.888 ms vs 281.678 ms (104.790 ms faster), recall@10=1.000
- `compressed-reranked-hybrid` vs `exact-hybrid`: 163.142 ms vs 281.678 ms (118.536 ms faster), recall@10=1.000
- Phase breakdown (compressed): sealed=159.963 ms, mutable=0.029 ms

## ivf-enabled
- `compressed-hybrid` vs `exact-hybrid`: 47.380 ms vs 288.611 ms (241.231 ms faster), recall@10=1.000
- `compressed-reranked-hybrid` vs `exact-hybrid`: 49.785 ms vs 288.611 ms (238.826 ms faster), recall@10=1.000
- Phase breakdown (compressed): sealed=35.419 ms, mutable=0.024 ms

## IVF impact on compressed-hybrid
- 176.888 ms → 47.380 ms (129.508 ms faster), candidates: 10.0 → 10.0
