# Architecture Flow

This is the current high-level flow through the prototype.

## Write path

1. upsert or delete arrives
2. write is appended to the write log
3. mutable buffer reflects latest-visible state
4. flush seals live mutable entries into local segment files
5. shard manifests point at active segments

## Query path

1. request enters the best API surface
2. exact, compressed, or reranked hybrid mode is selected
3. mutable state and sealed segments are searched together
4. scored hits and diagnostics are returned
5. reports and tests validate behavior across benchmark tiers

## Benchmark path

1. synthetic fixture is loaded
2. quantizer family is selected
3. local database is populated and flushed
4. exact vs compressed behavior is measured
5. Markdown and JSON report artifacts are exported under `reports/`
