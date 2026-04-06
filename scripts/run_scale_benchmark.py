"""Scale benchmark: RecallLayer at 100k, 500k, and 1M synthetic vectors.

Usage:
    python scripts/run_scale_benchmark.py [--scale 100k|500k|1m] [--dim 128] [--top-k 10]

Measures:
    - Insert throughput (vectors/sec) across flush cycles
    - Compressed-hybrid query latency (p50/p95/p99) over N queries
    - Recall@k vs exact search baseline (first 10 queries)
    - WAL line-count growth during insert phase
    - Sealed-segment count after all flushes
    - Mutable-buffer high-water mark

Notes:
    RecallLayer uses Python JSONL-backed segments.  Query latency is O(n) per
    segment in the worst case; the segment cache reduces repeat-query cost.
    These numbers honestly reflect prototype-grade Python storage performance,
    not a compiled vector-DB.  The benchmark is designed to stress the flush,
    compaction, and cache paths and surface memory/latency bottlenecks.
"""
from __future__ import annotations

import argparse
import os
import statistics
import tempfile
import time
from dataclasses import dataclass, field
from typing import List

import numpy as np

from recalllayer.engine.showcase_scored_db import ShowcaseScoredDatabase


# ---------------------------------------------------------------------------
# Dataset generation
# ---------------------------------------------------------------------------

def _rng_vectors(n: int, dim: int, seed: int = 42) -> np.ndarray:
    """Return an (n, dim) float32 array of L2-normalised random vectors."""
    rng = np.random.default_rng(seed)
    vecs = rng.standard_normal((n, dim)).astype(np.float32)
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    return vecs / np.where(norms > 0, norms, 1.0)


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------

@dataclass
class PhaseResult:
    phase: str
    n_vectors: int
    dim: int
    insert_sec: float
    insert_throughput: float           # vectors / second
    flush_count: int
    segment_count: int
    wal_peak_lines: int                # max WAL lines seen between auto-flushes
    query_latencies_ms: list[float] = field(default_factory=list)
    recall_at_k: float = 0.0
    top_k: int = 10

    @property
    def p50_ms(self) -> float:
        return statistics.median(self.query_latencies_ms) if self.query_latencies_ms else 0.0

    @property
    def p95_ms(self) -> float:
        if not self.query_latencies_ms:
            return 0.0
        s = sorted(self.query_latencies_ms)
        return s[max(0, int(len(s) * 0.95) - 1)]

    @property
    def p99_ms(self) -> float:
        if not self.query_latencies_ms:
            return 0.0
        s = sorted(self.query_latencies_ms)
        return s[max(0, int(len(s) * 0.99) - 1)]


# ---------------------------------------------------------------------------
# Benchmark runner
# ---------------------------------------------------------------------------

def run_phase(
    *,
    n_vectors: int,
    dim: int,
    flush_every: int,
    top_k: int,
    n_queries: int,
    root_dir: str,
    enable_ivf: bool = False,
    n_recall_queries: int = 10,
) -> PhaseResult:
    label = (
        f"{n_vectors // 1_000_000}M"
        if n_vectors >= 1_000_000
        else f"{n_vectors // 1_000}k"
    )
    print(f"\n{'='*62}")
    print(f"  Phase: {label} vectors  |  dim={dim}  |  flush_every={flush_every:,}")
    print(f"{'='*62}")

    # Generate all vectors upfront so generation time is excluded.
    print(f"  Generating {n_vectors:,} vectors ({dim}d)…", end=" ", flush=True)
    t0 = time.perf_counter()
    vectors = _rng_vectors(n_vectors, dim)
    queries = _rng_vectors(n_queries, dim, seed=99)
    print(f"done ({time.perf_counter() - t0:.1f}s)")

    # Cache enough segments to hold the whole index in memory.
    expected_segments = (n_vectors // flush_every) + 2
    db = ShowcaseScoredDatabase(
        collection_id="scale-bench",
        root_dir=root_dir,
        flush_threshold=flush_every,
        enable_ivf=enable_ivf,
        segment_cache_size=expected_segments,
        enable_segment_cache=True,
    )

    # --- Insert phase ---
    print(f"  Inserting {n_vectors:,} vectors…")
    wal_peak_lines = 0
    t0 = time.perf_counter()
    for i in range(n_vectors):
        db.upsert(
            vector_id=f"v{i}",
            embedding=vectors[i].tolist(),
            metadata={"bucket": i % 16},
        )
        if (i + 1) % 50_000 == 0:
            pct = (i + 1) / n_vectors * 100
            elapsed = time.perf_counter() - t0
            rate = (i + 1) / elapsed
            wal_lines = _wal_line_count(db)
            wal_peak_lines = max(wal_peak_lines, wal_lines)
            print(f"    {i+1:>8,} / {n_vectors:,}  ({pct:4.0f}%)  "
                  f"{rate:,.0f} vec/s  WAL={wal_lines} lines")

    insert_sec = time.perf_counter() - t0
    throughput = n_vectors / insert_sec

    # Flush remaining mutable state.
    seg_counter = db._auto_flush_segment_counter + 1
    remaining = len(db.mutable_buffer.all_entries())
    if remaining > 0:
        db.flush_mutable(
            segment_id="seg-final",
            generation=seg_counter,
            truncate_write_log=True,
        )
    wal_lines_final = _wal_line_count(db)
    wal_peak_lines = max(wal_peak_lines, wal_lines_final)
    flush_count = db._auto_flush_segment_counter + (1 if remaining > 0 else 0)
    segment_count = len(db._segment_paths())

    print(f"  Insert done: {throughput:,.0f} vec/s  ({insert_sec:.1f}s total)")
    print(f"  Flushes: {flush_count}  |  Segments: {segment_count}  |  WAL peak: {wal_peak_lines} lines")

    # --- Query phase ---
    print(f"  Running {n_queries} compressed-hybrid queries (top_k={top_k})…")

    # Warmup: one query to prime the segment cache.
    db.query_compressed_hybrid_hits(queries[0].tolist(), top_k=top_k)

    latencies: list[float] = []
    correct = 0
    total_recall_hits = 0

    for qi in range(n_queries):
        qvec = queries[qi].tolist()

        t0 = time.perf_counter()
        approx_hits = db.query_compressed_hybrid_hits(qvec, top_k=top_k)
        latencies.append((time.perf_counter() - t0) * 1000.0)

        # Recall vs exact baseline (only first n_recall_queries for speed).
        if qi < n_recall_queries:
            exact_hits = db.query_exact_hybrid_hits(qvec, top_k=top_k)
            approx_ids = {c.vector_id for c in approx_hits}
            exact_ids = {c.vector_id for c in exact_hits}
            correct += len(approx_ids & exact_ids)
            total_recall_hits += len(exact_ids)

    recall = correct / total_recall_hits if total_recall_hits > 0 else 0.0
    p50 = statistics.median(latencies)
    p95 = sorted(latencies)[max(0, int(len(latencies) * 0.95) - 1)]
    p99 = sorted(latencies)[max(0, int(len(latencies) * 0.99) - 1)]

    print(f"  Query p50={p50:.1f}ms  p95={p95:.1f}ms  p99={p99:.1f}ms")
    print(f"  Recall@{top_k} (vs exact, first {n_recall_queries} queries): {recall:.3f}")

    return PhaseResult(
        phase=label,
        n_vectors=n_vectors,
        dim=dim,
        insert_sec=insert_sec,
        insert_throughput=throughput,
        flush_count=flush_count,
        segment_count=segment_count,
        wal_peak_lines=wal_peak_lines,
        query_latencies_ms=latencies,
        recall_at_k=recall,
        top_k=top_k,
    )


def _wal_line_count(db: ShowcaseScoredDatabase) -> int:
    """Count lines in the write log (proxy for unbounded WAL growth)."""
    path = db.write_log.path
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8") as f:
        return sum(1 for _ in f)


# ---------------------------------------------------------------------------
# Summary printer
# ---------------------------------------------------------------------------

def print_summary(results: list[PhaseResult]) -> None:
    print(f"\n{'='*72}")
    print("  SCALE BENCHMARK SUMMARY")
    print(f"{'='*72}")
    hdr = (
        f"{'Scale':>8}  {'dim':>5}  {'vec/s':>10}  "
        f"{'p50ms':>8}  {'p95ms':>8}  {'p99ms':>8}  "
        f"{'R@k':>6}  {'segs':>5}  {'WAL peak':>10}"
    )
    print(hdr)
    print("-" * len(hdr))
    for r in results:
        print(
            f"{r.phase:>8}  {r.dim:>5}  {r.insert_throughput:>10,.0f}  "
            f"{r.p50_ms:>8.1f}  {r.p95_ms:>8.1f}  {r.p99_ms:>8.1f}  "
            f"{r.recall_at_k:>6.3f}  {r.segment_count:>5}  "
            f"{r.wal_peak_lines:>8} ln"
        )
    print(f"{'='*72}")
    print()
    print("  Notes:")
    print("    - RecallLayer uses Python JSONL segments: query cost is O(n_vectors) per query")
    print("    - Segment cache primes after first query; p50 reflects warm-cache latency")
    print("    - WAL peak shows max lines between auto-flush cycles (should stay bounded)")
    print("    - Recall@k vs exact-hybrid baseline (compressed search is approximate)")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

SCALE_MAP = {
    "10k":  10_000,
    "100k": 100_000,
    "500k": 500_000,
    "1m":   1_000_000,
}

FLUSH_MAP = {
    10_000:    2_000,
    100_000:   10_000,
    500_000:   25_000,
    1_000_000: 50_000,
}

QUERY_MAP = {
    10_000:    50,
    100_000:   50,
    500_000:   20,
    1_000_000: 10,
}


def main() -> None:
    parser = argparse.ArgumentParser(description="RecallLayer scale benchmark")
    parser.add_argument(
        "--scale", choices=list(SCALE_MAP.keys()), nargs="+",
        default=["100k"],
        help="Scale(s) to run (default: 100k)",
    )
    parser.add_argument("--dim", type=int, default=64, help="Vector dimension (default: 64)")
    parser.add_argument("--top-k", type=int, default=10, help="Top-k for queries (default: 10)")
    parser.add_argument(
        "--ivf", action="store_true", default=False,
        help="Enable IVF clustering at flush time (slower inserts, faster queries)"
    )
    parser.add_argument(
        "--root-dir", default=None,
        help="Root dir for segments (default: temp dir, removed after run)",
    )
    args = parser.parse_args()

    results: list[PhaseResult] = []

    with tempfile.TemporaryDirectory(prefix="recalllayer_scale_") as tmp:
        root = args.root_dir or tmp
        for scale_label in args.scale:
            n = SCALE_MAP[scale_label]
            flush_every = FLUSH_MAP[n]
            n_queries = QUERY_MAP[n]
            phase_root = os.path.join(root, f"phase_{scale_label}")
            os.makedirs(phase_root, exist_ok=True)
            result = run_phase(
                n_vectors=n,
                dim=args.dim,
                flush_every=flush_every,
                top_k=args.top_k,
                n_queries=n_queries,
                root_dir=phase_root,
                enable_ivf=args.ivf,
            )
            results.append(result)

    print_summary(results)


if __name__ == "__main__":
    main()
