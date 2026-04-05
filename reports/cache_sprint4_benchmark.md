# Cache Sprint 4 Benchmark

| Fixture | Quantizer | Cache mode | Query path | Latency ms | Cache hit rate | File reads | Decode loads | Candidates | Rerank ms |
|---|---|---|---|---:|---:|---:|---:|---:|---:|
| tiny_fixture | scalar-int8-127 | cache-disabled | exact-hybrid | 0.909 | 0.000 | 12 | 12 | 2.0 | 0.000 |
| tiny_fixture | scalar-int8-127 | cache-disabled | compressed-hybrid | 0.877 | 0.000 | 12 | 12 | 2.0 | 0.000 |
| tiny_fixture | scalar-int8-127 | cache-disabled | compressed-reranked-hybrid | 1.293 | 0.000 | 18 | 18 | 8.0 | 0.431 |
| tiny_fixture | scalar-int8-127 | cache-enabled | exact-hybrid | 0.433 | 0.846 | 1 | 1 | 2.0 | 0.000 |
| tiny_fixture | scalar-int8-127 | cache-enabled | compressed-hybrid | 0.486 | 0.846 | 1 | 1 | 2.0 | 0.000 |
| tiny_fixture | scalar-int8-127 | cache-enabled | compressed-reranked-hybrid | 0.661 | 0.895 | 1 | 1 | 8.0 | 0.196 |
| tiny_fixture | normalized-scalar-int8-127 | cache-disabled | exact-hybrid | 0.970 | 0.000 | 12 | 12 | 2.0 | 0.000 |
| tiny_fixture | normalized-scalar-int8-127 | cache-disabled | compressed-hybrid | 1.176 | 0.000 | 12 | 12 | 2.0 | 0.000 |
| tiny_fixture | normalized-scalar-int8-127 | cache-disabled | compressed-reranked-hybrid | 1.719 | 0.000 | 18 | 18 | 8.0 | 0.516 |
| tiny_fixture | normalized-scalar-int8-127 | cache-enabled | exact-hybrid | 0.428 | 0.846 | 1 | 1 | 2.0 | 0.000 |
| tiny_fixture | normalized-scalar-int8-127 | cache-enabled | compressed-hybrid | 0.562 | 0.846 | 1 | 1 | 2.0 | 0.000 |
| tiny_fixture | normalized-scalar-int8-127 | cache-enabled | compressed-reranked-hybrid | 0.836 | 0.895 | 1 | 1 | 8.0 | 0.231 |
| clustered_fixture_16 | scalar-int8-127 | cache-disabled | exact-hybrid | 2.865 | 0.000 | 16 | 16 | 5.0 | 0.000 |
| clustered_fixture_16 | scalar-int8-127 | cache-disabled | compressed-hybrid | 3.025 | 0.000 | 16 | 16 | 5.0 | 0.000 |
| clustered_fixture_16 | scalar-int8-127 | cache-disabled | compressed-reranked-hybrid | 4.228 | 0.000 | 24 | 24 | 20.0 | 1.305 |
| clustered_fixture_16 | scalar-int8-127 | cache-enabled | exact-hybrid | 0.682 | 0.882 | 1 | 1 | 5.0 | 0.000 |
| clustered_fixture_16 | scalar-int8-127 | cache-enabled | compressed-hybrid | 1.088 | 0.882 | 1 | 1 | 5.0 | 0.000 |
| clustered_fixture_16 | scalar-int8-127 | cache-enabled | compressed-reranked-hybrid | 1.313 | 0.920 | 1 | 1 | 20.0 | 0.258 |
| clustered_fixture_16 | normalized-scalar-int8-127 | cache-disabled | exact-hybrid | 3.157 | 0.000 | 16 | 16 | 5.0 | 0.000 |
| clustered_fixture_16 | normalized-scalar-int8-127 | cache-disabled | compressed-hybrid | 4.689 | 0.000 | 16 | 16 | 5.0 | 0.000 |
| clustered_fixture_16 | normalized-scalar-int8-127 | cache-disabled | compressed-reranked-hybrid | 5.894 | 0.000 | 24 | 24 | 20.0 | 1.585 |
| clustered_fixture_16 | normalized-scalar-int8-127 | cache-enabled | exact-hybrid | 0.900 | 0.882 | 1 | 1 | 5.0 | 0.000 |
| clustered_fixture_16 | normalized-scalar-int8-127 | cache-enabled | compressed-hybrid | 2.135 | 0.882 | 1 | 1 | 5.0 | 0.000 |
| clustered_fixture_16 | normalized-scalar-int8-127 | cache-enabled | compressed-reranked-hybrid | 2.471 | 0.920 | 1 | 1 | 20.0 | 0.389 |
