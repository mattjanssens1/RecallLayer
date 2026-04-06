| Scenario | Size | Dim | Shards | Delete % | Exact ms | Compressed ms | Compressed R@1 | Compressed R@10 | Reranked ms | Reranked R@10 | Storage bytes |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| small-2d-single-shard | 128 | 2 | 1 | 0.0 | 7.346 | 7.165 | 1.000 | 1.000 | 5.793 | 1.000 | 22904 |
| medium-16d-ivf | 512 | 16 | 1 | 0.0 | 20.595 | 12.225 | 1.000 | 0.969 | 22.059 | 0.988 | 135889 |
| medium-16d-ivf-deletes | 512 | 16 | 2 | 20.0 | 8.610 | 5.550 | 0.938 | 0.925 | 10.610 | 1.000 | 124489 |
| large-32d-ivf-multishard | 1024 | 32 | 4 | 10.0 | 14.813 | 7.667 | 0.917 | 0.854 | 14.883 | 1.000 | 384253 |
