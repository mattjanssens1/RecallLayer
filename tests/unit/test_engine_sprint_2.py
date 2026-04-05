"""Tests for engine sprint 2 features:
1. CompactionPolicy (background compaction trigger)
2. Multi-shard support
3. Write-log truncation
4. Collection-level stats
5. Segment format versioning
"""
from __future__ import annotations

from pathlib import Path

import pytest

from recalllayer.engine.compaction_executor import CompactionExecutor
from recalllayer.engine.compaction_planner import CompactionPlanner
from recalllayer.engine.compaction_policy import CompactionPolicy, CompactionThresholds
from recalllayer.engine.compactor import LocalSegmentCompactor
from recalllayer.engine.local_db import LocalVectorDatabase
from recalllayer.engine.sealed_segments import SEGMENT_FORMAT_VERSION, SegmentBuilder, SegmentReader
from recalllayer.quantization.scalar import ScalarQuantizer


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_db(tmp_path: Path, **kwargs) -> LocalVectorDatabase:
    return LocalVectorDatabase(collection_id="test", root_dir=tmp_path, **kwargs)


# ---------------------------------------------------------------------------
# 1. CompactionPolicy
# ---------------------------------------------------------------------------

class TestCompactionPolicy:
    def _setup(self, tmp_path: Path) -> tuple[LocalVectorDatabase, CompactionPolicy]:
        db = _make_db(tmp_path)
        # Write two vectors, flush twice to create 2 segments
        db.upsert(vector_id="a", embedding=[1.0, 0.0])
        db.flush_mutable(shard_id="shard-0", segment_id="seg-1", generation=1)
        db.upsert(vector_id="b", embedding=[0.0, 1.0])
        db.flush_mutable(shard_id="shard-0", segment_id="seg-2", generation=2)
        # Delete one to raise delete ratio
        db.upsert(vector_id="c", embedding=[0.5, 0.5])
        db.flush_mutable(shard_id="shard-0", segment_id="seg-3", generation=3)
        db.delete(vector_id="c")
        db.flush_mutable(shard_id="shard-0", segment_id="seg-4", generation=4)

        executor = CompactionExecutor(
            planner=CompactionPlanner(min_segment_count=2, min_delete_ratio=0.0),
            compactor=LocalSegmentCompactor(
                segments_root=tmp_path / "segments",
                manifests_root=tmp_path / "manifests",
            ),
            manifest_store=db.manifest_store,
            segment_manifest_store=db.segment_manifest_store,
        )

        thresholds = CompactionThresholds(min_segment_count=2, min_delete_ratio=0.0)
        policy = CompactionPolicy(executor=executor, thresholds=thresholds)
        return db, policy

    def test_policy_triggers_when_thresholds_exceeded(self, tmp_path: Path) -> None:
        _db, policy = self._setup(tmp_path)
        result = policy.maybe_compact(collection_id="test", shard_id="shard-0", output_segment_id="seg-merged", generation=10)
        assert result is not None
        assert result.updated_shard_manifest is not None

    def test_policy_skips_when_below_threshold(self, tmp_path: Path) -> None:
        db = _make_db(tmp_path)
        # Only one segment — should not trigger
        db.upsert(vector_id="x", embedding=[1.0, 0.0])
        db.flush_mutable(shard_id="shard-0", segment_id="seg-1", generation=1)

        executor = CompactionExecutor(
            planner=CompactionPlanner(min_segment_count=3, min_delete_ratio=0.0),
            compactor=LocalSegmentCompactor(
                segments_root=tmp_path / "segments",
                manifests_root=tmp_path / "manifests",
            ),
            manifest_store=db.manifest_store,
            segment_manifest_store=db.segment_manifest_store,
        )

        thresholds = CompactionThresholds(min_segment_count=3, min_delete_ratio=0.5)
        policy = CompactionPolicy(executor=executor, thresholds=thresholds)
        result = policy.maybe_compact(collection_id="test", shard_id="shard-0")
        assert result is None

    def test_policy_returns_none_with_no_manifest(self, tmp_path: Path) -> None:
        db = _make_db(tmp_path)
        executor = CompactionExecutor(
            planner=CompactionPlanner(min_segment_count=2, min_delete_ratio=0.0),
            compactor=LocalSegmentCompactor(
                segments_root=tmp_path / "segments",
                manifests_root=tmp_path / "manifests",
            ),
            manifest_store=db.manifest_store,
            segment_manifest_store=db.segment_manifest_store,
        )
        policy = CompactionPolicy(executor=executor)
        result = policy.maybe_compact(collection_id="test", shard_id="shard-0")
        assert result is None


# ---------------------------------------------------------------------------
# 2. Multi-shard support
# ---------------------------------------------------------------------------

class TestMultiShard:
    def test_write_and_query_separate_shards(self, tmp_path: Path) -> None:
        db = _make_db(tmp_path)
        db.upsert(vector_id="shard0-a", embedding=[1.0, 0.0], shard_id="shard-0")
        db.upsert(vector_id="shard1-a", embedding=[1.0, 0.0], shard_id="shard-1")

        results_0 = db.query_exact([1.0, 0.0], top_k=5, shard_id="shard-0")
        results_1 = db.query_exact([1.0, 0.0], top_k=5, shard_id="shard-1")

        assert "shard0-a" in results_0
        assert "shard1-a" not in results_0
        assert "shard1-a" in results_1
        assert "shard0-a" not in results_1

    def test_shard_isolation_after_flush(self, tmp_path: Path) -> None:
        db = _make_db(tmp_path)
        db.upsert(vector_id="alpha", embedding=[1.0, 0.0], shard_id="shard-0")
        db.upsert(vector_id="beta", embedding=[0.0, 1.0], shard_id="shard-1")
        db.flush_mutable(shard_id="shard-0", segment_id="seg-s0", generation=1)
        db.flush_mutable(shard_id="shard-1", segment_id="seg-s1", generation=1)

        m0, segs0 = db.load_manifest_set(shard_id="shard-0")
        m1, segs1 = db.load_manifest_set(shard_id="shard-1")
        assert m0 is not None
        assert m1 is not None
        assert "seg-s0" in m0.active_segment_ids
        assert "seg-s1" in m1.active_segment_ids
        assert "seg-s1" not in m0.active_segment_ids
        assert "seg-s0" not in m1.active_segment_ids

    def test_delete_targets_correct_shard(self, tmp_path: Path) -> None:
        db = _make_db(tmp_path)
        db.upsert(vector_id="shared-id", embedding=[1.0, 0.0], shard_id="shard-0")
        db.upsert(vector_id="shared-id", embedding=[1.0, 0.0], shard_id="shard-1")
        db.delete(vector_id="shared-id", shard_id="shard-0")

        r0 = db.query_exact([1.0, 0.0], top_k=5, shard_id="shard-0")
        r1 = db.query_exact([1.0, 0.0], top_k=5, shard_id="shard-1")
        assert "shared-id" not in r0
        assert "shared-id" in r1


# ---------------------------------------------------------------------------
# 3. Write-log truncation
# ---------------------------------------------------------------------------

class TestWriteLogTruncation:
    def test_truncate_removes_old_entries(self, tmp_path: Path) -> None:
        db = _make_db(tmp_path)
        db.upsert(vector_id="a", embedding=[1.0, 0.0])
        db.upsert(vector_id="b", embedding=[0.0, 1.0])
        epoch_after_b = db._write_epoch
        db.upsert(vector_id="c", embedding=[0.5, 0.5])

        removed = db.truncate_write_log_before(epoch_after_b)
        assert removed == 2  # a and b

        remaining = list(db.write_log.replay(after_write_epoch=0))
        assert len(remaining) == 1
        assert remaining[0].vector_id == "c"

    def test_truncate_write_log_flag_on_flush(self, tmp_path: Path) -> None:
        db = _make_db(tmp_path)
        db.upsert(vector_id="a", embedding=[1.0, 0.0])
        db.upsert(vector_id="b", embedding=[0.0, 1.0])
        db.flush_mutable(shard_id="shard-0", segment_id="seg-1", generation=1, truncate_write_log=True)

        remaining = list(db.write_log.replay(after_write_epoch=0))
        assert remaining == []  # all entries were flushed and truncated

    def test_recovery_still_works_after_truncation(self, tmp_path: Path) -> None:
        db = _make_db(tmp_path)
        db.upsert(vector_id="a", embedding=[1.0, 0.0])
        db.upsert(vector_id="b", embedding=[0.0, 1.0])
        flush_manifest = db.flush_mutable(shard_id="shard-0", segment_id="seg-1", generation=1, truncate_write_log=True)
        assert flush_manifest is not None

        # Write new entry after flush
        db.upsert(vector_id="c", embedding=[0.5, 0.5])

        # Simulate restart
        db2 = LocalVectorDatabase(collection_id="test", root_dir=tmp_path)
        applied = db2.recover()
        # Only "c" should be replayed (a, b were truncated)
        assert applied == 1
        ids = [e.record.vector_id for e in db2.mutable_buffer.all_entries()]
        assert "c" in ids
        assert "a" not in ids
        assert "b" not in ids

    def test_truncate_empty_log_is_safe(self, tmp_path: Path) -> None:
        db = _make_db(tmp_path)
        removed = db.truncate_write_log_before(999)
        assert removed == 0


# ---------------------------------------------------------------------------
# 4. Collection-level stats
# ---------------------------------------------------------------------------

class TestCollectionStats:
    def test_stats_after_writes_and_flush(self, tmp_path: Path) -> None:
        db = _make_db(tmp_path)
        db.upsert(vector_id="a", embedding=[1.0, 0.0])
        db.upsert(vector_id="b", embedding=[0.0, 1.0])
        db.flush_mutable(shard_id="shard-0", segment_id="seg-1", generation=1)

        stats = db.collection_stats()
        assert stats["total_segment_count"] == 1
        assert stats["total_live_rows"] == 2
        assert stats["total_delete_ratio"] == 0.0
        assert stats["mutable_buffer_size"] == 0
        assert stats["storage_bytes"] > 0

    def test_stats_reflect_deletes(self, tmp_path: Path) -> None:
        db = _make_db(tmp_path)
        db.upsert(vector_id="a", embedding=[1.0, 0.0])
        db.upsert(vector_id="b", embedding=[0.0, 1.0])
        db.flush_mutable(shard_id="shard-0", segment_id="seg-1", generation=1)
        # Mark b as deleted in segment manifest to simulate compaction awareness
        # Instead use the delete ratio tracking via segment manifests
        # We need to update live_row_count; the simplest way is via the segment_manifest_store
        seg_manifests = db.segment_manifest_store.list_manifests(collection_id="test", shard_id="shard-0")
        seg = seg_manifests[0]
        seg.live_row_count = 1
        seg.deleted_row_count = 1
        db.segment_manifest_store.save(seg)

        stats = db.collection_stats()
        assert stats["total_delete_ratio"] == pytest.approx(0.5)

    def test_stats_with_mutable_buffer(self, tmp_path: Path) -> None:
        db = _make_db(tmp_path)
        db.upsert(vector_id="x", embedding=[1.0, 0.0])
        stats = db.collection_stats()
        assert stats["mutable_buffer_size"] == 1
        assert stats["total_segment_count"] == 0

    def test_stats_multi_shard(self, tmp_path: Path) -> None:
        db = _make_db(tmp_path)
        db.upsert(vector_id="a", embedding=[1.0, 0.0], shard_id="shard-0")
        db.upsert(vector_id="b", embedding=[0.0, 1.0], shard_id="shard-1")
        db.flush_mutable(shard_id="shard-0", segment_id="seg-s0", generation=1)
        db.flush_mutable(shard_id="shard-1", segment_id="seg-s1", generation=1)

        stats = db.collection_stats()
        assert stats["total_segment_count"] == 2
        assert stats["total_live_rows"] == 2
        assert stats["shard_count"] == 2


# ---------------------------------------------------------------------------
# 5. Segment format versioning
# ---------------------------------------------------------------------------

class TestSegmentFormatVersioning:
    def _build_segment(self, tmp_path: Path):
        from recalllayer.engine.mutable_buffer import MutableBuffer

        buf = MutableBuffer(collection_id="test")
        buf.upsert(
            vector_id="v1",
            embedding=[1.0, 0.0],
            metadata={},
            embedding_version="embed-v1",
            quantizer_version="tq-v0",
            write_epoch=1,
        )
        builder = SegmentBuilder(tmp_path / "segments", quantizer=ScalarQuantizer())
        manifest, paths = builder.build(
            collection_id="test",
            shard_id="shard-0",
            segment_id="seg-v",
            generation=1,
            embedding_version="embed-v1",
            quantizer_version="tq-v0",
            entries=buf.all_entries(),
        )
        return paths.segment_path

    def test_written_segment_has_correct_version(self, tmp_path: Path) -> None:
        seg_path = self._build_segment(tmp_path)
        reader = SegmentReader(seg_path)
        assert reader.read_format_version() == SEGMENT_FORMAT_VERSION

    def test_reader_can_read_versioned_segment(self, tmp_path: Path) -> None:
        seg_path = self._build_segment(tmp_path)
        reader = SegmentReader(seg_path)
        vectors = list(reader.iter_indexed_vectors())
        assert len(vectors) == 1
        assert vectors[0].vector_id == "v1"

    def test_reader_raises_on_unknown_version(self, tmp_path: Path) -> None:
        seg_path = self._build_segment(tmp_path)
        # Tamper with the header
        content = seg_path.read_text()
        tampered = content.replace(f'"format_version":"{SEGMENT_FORMAT_VERSION}"', '"format_version":"v999"')
        seg_path.write_text(tampered)

        reader = SegmentReader(seg_path)
        with pytest.raises(ValueError, match="Unknown segment format version"):
            list(reader.iter_indexed_vectors())

    def test_reader_handles_missing_header_gracefully(self, tmp_path: Path) -> None:
        # Old-style segment without header — should not crash
        seg_path = tmp_path / "old.segment.jsonl"
        import json
        from recalllayer.quantization.scalar import ScalarQuantizer as SQ
        q = SQ()
        enc = q.encode([1.0, 0.0])
        row = {
            "local_docno": 0,
            "vector_id": "old-v",
            "codes": enc.codes.tolist(),
            "scale": enc.scale,
            "metadata": {},
            "write_epoch": 1,
        }
        seg_path.write_text(json.dumps(row) + "\n")
        reader = SegmentReader(seg_path)
        vectors = list(reader.iter_indexed_vectors())
        assert len(vectors) == 1
        assert vectors[0].vector_id == "old-v"
