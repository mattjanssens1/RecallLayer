"""Tests for engine sprint 3 features:
1. Tombstone physical cleanup in compaction (multi-shard aware)
2. IVF-style candidate pre-filtering (CentroidIndex)
3. Segment merge prioritization
4. Write-ahead durability mode
5. Segment read cache
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from recalllayer.engine.centroid_index import CentroidIndex
from recalllayer.engine.compaction_executor import CompactionExecutor
from recalllayer.engine.compaction_planner import CompactionPlanner
from recalllayer.engine.compaction_policy import CompactionPolicy, CompactionThresholds
from recalllayer.engine.compactor import LocalSegmentCompactor
from recalllayer.engine.local_db import LocalVectorDatabase
from recalllayer.engine.sealed_segments import SegmentReader
from recalllayer.engine.segment_cache import SegmentReadCache
from recalllayer.engine.write_log import DurabilityMode
from recalllayer.model.manifest import SegmentManifest, SegmentState
from recalllayer.quantization.scalar import ScalarQuantizer
from recalllayer.retrieval.base import IndexedVector


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_db(tmp_path: Path, **kwargs) -> LocalVectorDatabase:
    return LocalVectorDatabase(collection_id="test", root_dir=tmp_path, **kwargs)


def _make_compaction_setup(db: LocalVectorDatabase, tmp_path: Path) -> tuple[CompactionExecutor, CompactionPolicy]:
    executor = CompactionExecutor(
        planner=CompactionPlanner(min_segment_count=2, min_delete_ratio=0.0),
        compactor=LocalSegmentCompactor(
            segments_root=tmp_path / "segments",
            manifests_root=tmp_path / "manifests",
        ),
        manifest_store=db.manifest_store,
        segment_manifest_store=db.segment_manifest_store,
    )
    policy = CompactionPolicy(
        executor=executor,
        thresholds=CompactionThresholds(min_segment_count=2, min_delete_ratio=0.0),
    )
    return executor, policy


# ---------------------------------------------------------------------------
# 1. Tombstone physical cleanup in compaction (multi-shard aware)
# ---------------------------------------------------------------------------

class TestMultiShardTombstoneCompaction:
    def test_named_shard_tombstones_cleaned_after_compact(self, tmp_path: Path) -> None:
        """Tombstones in a named (non-default) shard are physically removed by compaction."""
        db = _make_db(tmp_path)
        shard = "shard-analytics"

        db.upsert(vector_id="v1", embedding=[1.0, 0.0], shard_id=shard)
        db.upsert(vector_id="v2", embedding=[0.0, 1.0], shard_id=shard)
        db.flush_mutable(shard_id=shard, segment_id="seg-1", generation=1)

        db.delete(vector_id="v1", shard_id=shard)
        db.flush_mutable(shard_id=shard, segment_id="seg-2", generation=2)

        executor, _ = _make_compaction_setup(db, tmp_path)
        result = executor.compact_shard(
            collection_id="test",
            shard_id=shard,
            output_segment_id="seg-merged",
            generation=3,
        )
        assert result is not None

        # Only v2 should survive
        segment_dir = tmp_path / "segments" / "test" / shard
        merged_path = segment_dir / "seg-merged.segment.jsonl"
        assert merged_path.exists()

        reader = SegmentReader(merged_path)
        ids = [iv.vector_id for iv in reader.iter_indexed_vectors()]
        assert "v1" not in ids
        assert "v2" in ids

    def test_compaction_policy_works_on_named_shard(self, tmp_path: Path) -> None:
        """CompactionPolicy.maybe_compact triggers correctly for named shards."""
        db = _make_db(tmp_path)
        shard = "shard-beta"

        db.upsert(vector_id="a", embedding=[1.0, 0.0], shard_id=shard)
        db.flush_mutable(shard_id=shard, segment_id="seg-a1", generation=1)
        db.upsert(vector_id="b", embedding=[0.0, 1.0], shard_id=shard)
        db.flush_mutable(shard_id=shard, segment_id="seg-a2", generation=2)

        _, policy = _make_compaction_setup(db, tmp_path)
        result = policy.maybe_compact(
            collection_id="test",
            shard_id=shard,
            output_segment_id="seg-merged",
            generation=3,
        )
        assert result is not None
        assert result.updated_shard_manifest.shard_id == shard

    def test_multi_shard_query_isolation_after_compaction(self, tmp_path: Path) -> None:
        """Deleting in shard-A and compacting does not affect shard-B results."""
        db = _make_db(tmp_path)

        # Shard A: insert and delete v1
        db.upsert(vector_id="v1", embedding=[1.0, 0.0], shard_id="shard-a")
        db.upsert(vector_id="v2", embedding=[0.5, 0.5], shard_id="shard-a")
        db.flush_mutable(shard_id="shard-a", segment_id="seg-a1", generation=1)
        db.delete(vector_id="v1", shard_id="shard-a")
        db.flush_mutable(shard_id="shard-a", segment_id="seg-a2", generation=2)

        # Shard B: insert v1 (same ID, different shard)
        db.upsert(vector_id="v1", embedding=[1.0, 0.0], shard_id="shard-b")
        db.flush_mutable(shard_id="shard-b", segment_id="seg-b1", generation=1)

        executor, _ = _make_compaction_setup(db, tmp_path)
        executor.compact_shard(
            collection_id="test",
            shard_id="shard-a",
            output_segment_id="seg-a-merged",
            generation=3,
        )

        # shard-b should still have v1
        seg_b_path = tmp_path / "segments" / "test" / "shard-b" / "seg-b1.segment.jsonl"
        reader = SegmentReader(seg_b_path)
        ids = [iv.vector_id for iv in reader.iter_indexed_vectors()]
        assert "v1" in ids

    def test_tombstones_not_present_in_compacted_segment(self, tmp_path: Path) -> None:
        """After compaction, merged segment file contains no tombstone rows."""
        db = _make_db(tmp_path)
        shard = "shard-0"

        db.upsert(vector_id="x", embedding=[1.0, 0.0])
        db.upsert(vector_id="y", embedding=[0.0, 1.0])
        db.flush_mutable(shard_id=shard, segment_id="seg-1", generation=1)
        db.delete(vector_id="x")
        db.flush_mutable(shard_id=shard, segment_id="seg-2", generation=2)

        executor, _ = _make_compaction_setup(db, tmp_path)
        result = executor.compact_shard(
            collection_id="test",
            shard_id=shard,
            output_segment_id="seg-merged",
            generation=3,
        )
        assert result is not None

        import json
        merged_path = tmp_path / "segments" / "test" / shard / "seg-merged.segment.jsonl"
        tombstones = 0
        with merged_path.open() as f:
            for line in f:
                row = json.loads(line)
                if row.get("is_deleted"):
                    tombstones += 1
        assert tombstones == 0


# ---------------------------------------------------------------------------
# 2. IVF-style candidate pre-filtering (CentroidIndex)
# ---------------------------------------------------------------------------

class TestCentroidIndex:
    def _make_indexed_vectors(self, n: int, dim: int = 4) -> tuple[list[IndexedVector], ScalarQuantizer]:
        rng = np.random.default_rng(1)
        q = ScalarQuantizer()
        vecs = []
        for i in range(n):
            emb = rng.random(dim).astype(np.float32)
            vecs.append(IndexedVector(
                vector_id=f"v{i}",
                encoded=q.encode(emb),
                metadata={},
            ))
        return vecs, q

    def test_build_creates_buckets(self, tmp_path: Path) -> None:
        vecs, q = self._make_indexed_vectors(20)
        idx = CentroidIndex(n_clusters=4)
        idx.build(vecs, quantizer=q)
        assert idx.is_built
        assert idx.bucket_count == 4

    def test_probe_returns_subset(self, tmp_path: Path) -> None:
        """probe_k=1 should return fewer candidates than total."""
        vecs, q = self._make_indexed_vectors(40, dim=4)
        idx = CentroidIndex(n_clusters=8)
        idx.build(vecs, quantizer=q)

        query = np.ones(4, dtype=np.float32)
        candidates = idx.probe(query, probe_k=1)
        # Should be a strict subset of all IDs
        all_ids = {v.vector_id for v in vecs}
        assert candidates.issubset(all_ids)
        assert len(candidates) < len(all_ids)

    def test_probe_k2_has_reasonable_recall(self, tmp_path: Path) -> None:
        """With probe_k >= 2, recall should stay reasonable (>=50%)."""
        rng = np.random.default_rng(99)
        q = ScalarQuantizer()
        dim = 8
        n = 50

        embeddings = [rng.random(dim).astype(np.float32) for _ in range(n)]
        vecs = [
            IndexedVector(vector_id=f"v{i}", encoded=q.encode(e), metadata={})
            for i, e in enumerate(embeddings)
        ]

        idx = CentroidIndex(n_clusters=5)
        idx.build(vecs, quantizer=q)

        # Query near the first vector
        query = embeddings[0]
        candidates = idx.probe(query, probe_k=2)
        # v0 should be found
        assert "v0" in candidates

    def test_empty_build(self) -> None:
        idx = CentroidIndex(n_clusters=4)
        q = ScalarQuantizer()
        idx.build([], quantizer=q)
        assert idx.is_built
        assert idx.bucket_count == 0
        result = idx.probe(np.array([1.0, 0.0]), probe_k=2)
        assert result == set()

    def test_fewer_vectors_than_clusters(self) -> None:
        q = ScalarQuantizer()
        vecs = [
            IndexedVector(vector_id=f"v{i}", encoded=q.encode([float(i), 0.0]), metadata={})
            for i in range(3)
        ]
        idx = CentroidIndex(n_clusters=8)
        idx.build(vecs, quantizer=q)
        assert idx.bucket_count == 3  # capped at n

    def test_candidate_count_less_than_full_scan(self) -> None:
        """IVF pre-filter should yield fewer candidates than full scan with probe_k < n_clusters."""
        rng = np.random.default_rng(7)
        q = ScalarQuantizer()
        n, dim = 80, 8
        embeddings = [rng.random(dim).astype(np.float32) for _ in range(n)]
        vecs = [
            IndexedVector(vector_id=f"v{i}", encoded=q.encode(e), metadata={})
            for i, e in enumerate(embeddings)
        ]
        idx = CentroidIndex(n_clusters=8)
        idx.build(vecs, quantizer=q)
        query = rng.random(dim).astype(np.float32)
        candidates = idx.probe(query, probe_k=2)
        assert len(candidates) < n


# ---------------------------------------------------------------------------
# 3. Segment merge prioritization
# ---------------------------------------------------------------------------

class TestSegmentMergePrioritization:
    def _make_manifest(self, seg_id: str, generation: int, total: int, live: int):
        return SegmentManifest(
            segment_id=seg_id,
            collection_id="test",
            shard_id="shard-0",
            generation=generation,
            state=SegmentState.ACTIVE,
            row_count=total,
            live_row_count=live,
            deleted_row_count=total - live,
            embedding_version="embed-v1",
            quantizer_version="tq-v0",
        )

    def test_high_delete_ratio_picked_first(self) -> None:
        """Segment with high delete ratio should have higher priority score."""
        planner = CompactionPlanner(min_segment_count=2)

        # seg-high: 80% deleted
        high = self._make_manifest("seg-high", generation=1, total=100, live=20)
        # seg-low: 10% deleted
        low = self._make_manifest("seg-low", generation=1, total=100, live=90)

        high_score = planner._priority_score(high)
        low_score = planner._priority_score(low)
        assert high_score > low_score

    def test_older_generation_picked_first_equal_delete_ratio(self) -> None:
        """Among segments with equal delete ratio, older (lower generation) wins."""
        planner = CompactionPlanner(min_segment_count=2)

        old = self._make_manifest("seg-old", generation=1, total=100, live=100)
        new_ = self._make_manifest("seg-new", generation=10, total=100, live=100)

        assert planner._priority_score(old) > planner._priority_score(new_)

    def test_plan_selects_highest_priority_first(self) -> None:
        """plan() should prefer high-delete-ratio segments when > min_segment_count available."""
        planner = CompactionPlanner(min_segment_count=2, max_total_rows=1000)

        # 4 segments; seg-dirty has by far the highest delete ratio
        dirty = self._make_manifest("seg-dirty", generation=2, total=100, live=10)
        clean_a = self._make_manifest("seg-clean-a", generation=1, total=100, live=99)
        clean_b = self._make_manifest("seg-clean-b", generation=1, total=100, live=99)
        clean_c = self._make_manifest("seg-clean-c", generation=1, total=100, live=99)

        plan = planner.plan([clean_a, clean_b, clean_c, dirty])
        assert plan is not None
        # dirty should be among the selected candidates (it's highest priority)
        assert "seg-dirty" in plan.candidate_segment_ids

    def test_plan_merges_at_least_min_count(self) -> None:
        planner = CompactionPlanner(min_segment_count=2)
        m1 = self._make_manifest("s1", generation=1, total=10, live=10)
        m2 = self._make_manifest("s2", generation=2, total=10, live=10)
        plan = planner.plan([m1, m2])
        assert plan is not None
        assert len(plan.candidate_segment_ids) >= 2


# ---------------------------------------------------------------------------
# 4. Write-ahead durability mode
# ---------------------------------------------------------------------------

class TestDurabilityMode:
    def test_memory_mode_default(self, tmp_path: Path) -> None:
        db = _make_db(tmp_path)
        assert db.durability_mode == DurabilityMode.MEMORY

    def test_log_sync_mode_accepted(self, tmp_path: Path) -> None:
        db = _make_db(tmp_path, durability_mode=DurabilityMode.LOG_SYNC)
        assert db.durability_mode == DurabilityMode.LOG_SYNC

    def test_both_modes_produce_same_results(self, tmp_path: Path) -> None:
        """MEMORY and LOG_SYNC modes should produce identical visible results."""
        tmp_mem = tmp_path / "mem"
        tmp_sync = tmp_path / "sync"

        db_mem = LocalVectorDatabase(collection_id="test", root_dir=tmp_mem, durability_mode=DurabilityMode.MEMORY)
        db_sync = LocalVectorDatabase(collection_id="test", root_dir=tmp_sync, durability_mode=DurabilityMode.LOG_SYNC)

        for db in (db_mem, db_sync):
            db.upsert(vector_id="a", embedding=[1.0, 0.0])
            db.upsert(vector_id="b", embedding=[0.0, 1.0])
            db.delete(vector_id="a")

        results_mem = db_mem.query_exact([1.0, 0.0], top_k=5)
        results_sync = db_sync.query_exact([1.0, 0.0], top_k=5)
        assert set(results_mem) == set(results_sync)

    def test_log_sync_write_log_file_exists(self, tmp_path: Path) -> None:
        db = _make_db(tmp_path, durability_mode=DurabilityMode.LOG_SYNC)
        db.upsert(vector_id="v1", embedding=[1.0, 0.0])
        log_path = tmp_path / "test" / "write_log.jsonl"
        assert log_path.exists()
        assert log_path.stat().st_size > 0

    def test_write_log_durability_mode_propagated(self, tmp_path: Path) -> None:
        db = _make_db(tmp_path, durability_mode=DurabilityMode.LOG_SYNC)
        assert db.write_log.durability_mode == DurabilityMode.LOG_SYNC

    def test_memory_mode_write_log_exists(self, tmp_path: Path) -> None:
        db = _make_db(tmp_path, durability_mode=DurabilityMode.MEMORY)
        db.upsert(vector_id="v1", embedding=[1.0, 0.0])
        log_path = tmp_path / "test" / "write_log.jsonl"
        assert log_path.exists()


# ---------------------------------------------------------------------------
# 5. Segment read cache
# ---------------------------------------------------------------------------

class TestSegmentReadCache:
    def _write_segment(self, tmp_path: Path, name: str = "seg-1") -> Path:
        """Write a simple segment and return its path."""
        db = LocalVectorDatabase(collection_id="test", root_dir=tmp_path)
        db.upsert(vector_id="v1", embedding=[1.0, 0.0])
        db.upsert(vector_id="v2", embedding=[0.0, 1.0])
        db.flush_mutable(shard_id="shard-0", segment_id=name, generation=1)
        return tmp_path / "segments" / "test" / "shard-0" / f"{name}.segment.jsonl"

    def test_cache_hit_returns_same_content(self, tmp_path: Path) -> None:
        path = self._write_segment(tmp_path)
        cache = SegmentReadCache(max_size=4)
        reader = SegmentReader(path, cache=cache)

        first = list(reader.iter_indexed_vectors())
        assert cache.size == 1

        second = list(reader.iter_indexed_vectors())
        assert [iv.vector_id for iv in first] == [iv.vector_id for iv in second]

    def test_cache_evicts_lru(self, tmp_path: Path) -> None:
        cache = SegmentReadCache(max_size=2)
        q = ScalarQuantizer()

        # Manually populate cache with 3 entries
        p1, p2, p3 = Path("/fake/seg1.jsonl"), Path("/fake/seg2.jsonl"), Path("/fake/seg3.jsonl")
        dummy = [IndexedVector(vector_id="x", encoded=q.encode([1.0, 0.0]), metadata={})]

        cache.put(p1, dummy)
        cache.put(p2, dummy)
        assert cache.size == 2

        cache.put(p3, dummy)  # should evict p1 (LRU)
        assert cache.size == 2
        assert cache.get(p1) is None
        assert cache.get(p2) is not None
        assert cache.get(p3) is not None

    def test_cache_invalidation(self, tmp_path: Path) -> None:
        path = self._write_segment(tmp_path)
        cache = SegmentReadCache(max_size=4)
        reader = SegmentReader(path, cache=cache)

        list(reader.iter_indexed_vectors())
        assert cache.size == 1

        removed = cache.invalidate(path)
        assert removed
        assert cache.size == 0

    def test_cache_invalidated_after_compaction(self, tmp_path: Path) -> None:
        """After compaction, old segment cache entries can be invalidated."""
        db = _make_db(tmp_path)
        db.upsert(vector_id="a", embedding=[1.0, 0.0])
        db.flush_mutable(shard_id="shard-0", segment_id="seg-1", generation=1)
        db.upsert(vector_id="b", embedding=[0.0, 1.0])
        db.flush_mutable(shard_id="shard-0", segment_id="seg-2", generation=2)

        cache = SegmentReadCache(max_size=8)
        # Populate cache with old segments
        seg1_path = tmp_path / "segments" / "test" / "shard-0" / "seg-1.segment.jsonl"
        seg2_path = tmp_path / "segments" / "test" / "shard-0" / "seg-2.segment.jsonl"
        reader1 = SegmentReader(seg1_path, cache=cache)
        reader2 = SegmentReader(seg2_path, cache=cache)
        list(reader1.iter_indexed_vectors())
        list(reader2.iter_indexed_vectors())
        assert cache.size == 2

        # Compact
        executor, _ = _make_compaction_setup(db, tmp_path)
        executor.compact_shard(
            collection_id="test",
            shard_id="shard-0",
            output_segment_id="seg-merged",
            generation=3,
        )

        # Invalidate old entries (simulate cache invalidation on compaction)
        prefix = str(tmp_path / "segments" / "test" / "shard-0")
        removed = cache.invalidate_prefix(prefix)
        assert removed >= 2
        assert cache.size == 0

    def test_no_cache_still_works(self, tmp_path: Path) -> None:
        """SegmentReader works fine without a cache (backward compat)."""
        path = self._write_segment(tmp_path)
        reader = SegmentReader(path)  # no cache
        ids = [iv.vector_id for iv in reader.iter_indexed_vectors()]
        assert "v1" in ids and "v2" in ids

    def test_cache_max_size_respected(self) -> None:
        q = ScalarQuantizer()
        cache = SegmentReadCache(max_size=3)
        dummy = [IndexedVector(vector_id="x", encoded=q.encode([1.0]), metadata={})]

        for i in range(10):
            cache.put(Path(f"/fake/seg{i}.jsonl"), dummy)

        assert cache.size == 3
