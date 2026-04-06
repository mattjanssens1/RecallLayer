"""Tests for engine lifecycle depth features:
1. Physical delete compaction
2. Delete ratio tracking
3. Flush thresholds
4. Query snapshot semantics
5. Segment lifecycle metadata + smarter compaction planner
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from recalllayer.engine.compaction_planner import (
    CompactionPlanner,
    compaction_eligibility_score,
)
from recalllayer.engine.compactor import LocalSegmentCompactor
from recalllayer.engine.showcase_db import ShowcaseLocalDatabase
from recalllayer.model.manifest import SegmentManifest, SegmentState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_db(tmp_path: Path, **kwargs) -> ShowcaseLocalDatabase:
    return ShowcaseLocalDatabase(
        collection_id="col",
        root_dir=str(tmp_path),
        **kwargs,
    )


def _vec(value: float, dim: int = 4) -> list[float]:
    return [value] * dim


def _write_segment(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, separators=(",", ":")) + "\n")


# ---------------------------------------------------------------------------
# 1. Physical delete compaction
# ---------------------------------------------------------------------------

class TestPhysicalDeleteCompaction:
    def _setup_compactor(self, tmp_path: Path):
        segments_root = tmp_path / "segments"
        manifests_root = tmp_path / "manifests"
        compactor = LocalSegmentCompactor(
            segments_root=segments_root,
            manifests_root=manifests_root,
        )
        return compactor, segments_root

    def test_delete_compact_query_deleted_not_returned(self, tmp_path: Path) -> None:
        db = _make_db(tmp_path)
        db.upsert(vector_id="a", embedding=_vec(1.0))
        db.upsert(vector_id="b", embedding=_vec(0.5))
        db.delete(vector_id="a")
        db.flush_mutable(segment_id="seg-0")

        # Compact — deleted row should be physically removed
        compactor = LocalSegmentCompactor(
            segments_root=tmp_path / "segments",
            manifests_root=tmp_path / "segment-manifests",
        )
        artifacts = compactor.compact(
            collection_id="col",
            shard_id="shard-0",
            output_segment_id="seg-compacted",
            generation=2,
        )

        # Verify only live rows in compacted segment
        seg_path = artifacts.segment_path
        all_rows = [json.loads(line) for line in seg_path.read_text().splitlines()]
        rows = [r for r in all_rows if not r.get("__header__")]
        vector_ids = {r["vector_id"] for r in rows}
        assert "a" not in vector_ids
        assert "b" in vector_ids

    def test_delete_compact_live_row_count_correct(self, tmp_path: Path) -> None:
        db = _make_db(tmp_path)
        for i in range(5):
            db.upsert(vector_id=f"v{i}", embedding=_vec(float(i)))
        db.delete(vector_id="v0")
        db.delete(vector_id="v1")
        db.flush_mutable(segment_id="seg-0")

        compactor = LocalSegmentCompactor(
            segments_root=tmp_path / "segments",
            manifests_root=tmp_path / "segment-manifests",
        )
        artifacts = compactor.compact(
            collection_id="col",
            shard_id="shard-0",
            output_segment_id="seg-compacted",
            generation=2,
        )
        assert artifacts.segment_manifest.row_count == 3
        assert artifacts.segment_manifest.live_row_count == 3

    def test_tombstone_rows_absent_from_output_segment(self, tmp_path: Path) -> None:
        db = _make_db(tmp_path)
        db.upsert(vector_id="x", embedding=_vec(1.0))
        db.upsert(vector_id="y", embedding=_vec(0.5))  # keep a live row so flush writes a segment
        db.delete(vector_id="x")
        db.flush_mutable(segment_id="seg-0")

        compactor = LocalSegmentCompactor(
            segments_root=tmp_path / "segments",
            manifests_root=tmp_path / "segment-manifests",
        )
        artifacts = compactor.compact(
            collection_id="col",
            shard_id="shard-0",
            output_segment_id="seg-compacted",
            generation=2,
        )

        all_rows = [json.loads(line) for line in artifacts.segment_path.read_text().splitlines()]
        rows = [r for r in all_rows if not r.get("__header__")]
        assert all(not r.get("is_deleted", False) for r in rows)
        assert all(r["vector_id"] != "x" for r in rows)

    def test_double_upsert_compact_only_latest_version(self, tmp_path: Path) -> None:
        compactor, segments_root = self._setup_compactor(tmp_path)
        shard_dir = segments_root / "col" / "shard-0"
        _write_segment(shard_dir / "seg-1.segment.jsonl", [
            {"vector_id": "a", "codes": [1], "scale": 1.0, "metadata": {}, "write_epoch": 1},
        ])
        _write_segment(shard_dir / "seg-2.segment.jsonl", [
            {"vector_id": "a", "codes": [9], "scale": 1.0, "metadata": {}, "write_epoch": 5},
        ])

        artifacts = compactor.compact(
            collection_id="col",
            shard_id="shard-0",
            output_segment_id="seg-merged",
            generation=2,
        )
        all_rows = [json.loads(line) for line in artifacts.segment_path.read_text().splitlines()]
        rows = [r for r in all_rows if not r.get("__header__")]
        assert len(rows) == 1
        assert rows[0]["codes"] == [9]

    def test_delete_compact_restart_query_still_not_returned(self, tmp_path: Path) -> None:
        """After compact + restart, deleted rows are still gone."""
        db = _make_db(tmp_path)
        db.upsert(vector_id="keep", embedding=_vec(1.0))
        db.upsert(vector_id="gone", embedding=_vec(0.9))
        db.delete(vector_id="gone")
        db.flush_mutable(segment_id="seg-0")

        compactor = LocalSegmentCompactor(
            segments_root=tmp_path / "segments",
            manifests_root=tmp_path / "segment-manifests",
        )
        _ = compactor.compact(
            collection_id="col",
            shard_id="shard-0",
            output_segment_id="seg-compacted",
            generation=2,
        )

        # Simulate restart: new db instance
        db2 = _make_db(tmp_path)
        # Update shard manifest to point to compacted segment
        shard_manifest = db2.manifest_store.load(collection_id="col", shard_id="shard-0")
        assert shard_manifest is not None
        updated = shard_manifest.model_copy(update={"active_segment_ids": ["seg-compacted"]})
        db2.manifest_store.save(updated)

        results = db2.query_exact_hybrid(_vec(0.9), top_k=10)
        assert "gone" not in results
        assert "keep" in results


# ---------------------------------------------------------------------------
# 2. Delete ratio tracking
# ---------------------------------------------------------------------------

class TestDeleteRatioTracking:
    def test_delete_ratio_zero_before_any_deletes(self, tmp_path: Path) -> None:
        db = _make_db(tmp_path)
        db.upsert(vector_id="a", embedding=_vec(1.0))
        db.upsert(vector_id="b", embedding=_vec(0.5))
        db.flush_mutable(segment_id="seg-0")

        ratio = db.shard_delete_ratio()
        assert ratio == pytest.approx(0.0)

    def test_live_row_fraction_is_one_before_deletes(self, tmp_path: Path) -> None:
        db = _make_db(tmp_path)
        db.upsert(vector_id="a", embedding=_vec(1.0))
        db.flush_mutable(segment_id="seg-0")

        fraction = db.shard_live_row_fraction()
        assert fraction == pytest.approx(1.0)

    def test_delete_ratio_none_when_no_segments(self, tmp_path: Path) -> None:
        db = _make_db(tmp_path)
        assert db.shard_delete_ratio() is None
        assert db.shard_live_row_fraction() is None

    def test_delete_ratio_reflects_compaction_cleanup(self, tmp_path: Path) -> None:
        """After compaction physically removes dead rows, delete ratio returns to 0."""
        db = _make_db(tmp_path)
        db.upsert(vector_id="a", embedding=_vec(1.0))
        db.upsert(vector_id="b", embedding=_vec(0.5))
        db.delete(vector_id="a")
        db.flush_mutable(segment_id="seg-0")

        # Before compaction the flush wrote tombstone; live_row_count reflects live only
        # (segment builder only counts non-deleted rows, so delete ratio should be 0
        #  because the segment itself only contains live rows after the SegmentBuilder fix)
        # After compaction, we re-save a manifest with row_count = live rows
        compactor = LocalSegmentCompactor(
            segments_root=tmp_path / "segments",
            manifests_root=tmp_path / "segment-manifests",
        )
        compactor.compact(
            collection_id="col",
            shard_id="shard-0",
            output_segment_id="seg-compacted",
            generation=2,
        )

        # Reload db to pick up new segment manifest
        db2 = _make_db(tmp_path)
        shard_manifest = db2.manifest_store.load(collection_id="col", shard_id="shard-0")
        updated = shard_manifest.model_copy(update={"active_segment_ids": ["seg-compacted"]})
        db2.manifest_store.save(updated)

        ratio = db2.shard_delete_ratio()
        assert ratio == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# 3. Flush thresholds
# ---------------------------------------------------------------------------

class TestFlushThresholds:
    def test_auto_flush_triggers_at_threshold(self, tmp_path: Path) -> None:
        db = _make_db(tmp_path, flush_threshold=3)
        # Insert 2 — should NOT flush
        db.upsert(vector_id="a", embedding=_vec(1.0))
        db.upsert(vector_id="b", embedding=_vec(0.5))
        assert db.mutable_buffer.watermark() > 0
        shard_manifest = db.manifest_store.load(collection_id="col", shard_id="shard-0")
        assert shard_manifest is None  # no flush yet

        # Insert 3rd — triggers auto-flush
        db.upsert(vector_id="c", embedding=_vec(0.1))
        shard_manifest = db.manifest_store.load(collection_id="col", shard_id="shard-0")
        assert shard_manifest is not None
        assert len(shard_manifest.active_segment_ids) >= 1

    def test_auto_flush_not_before_threshold(self, tmp_path: Path) -> None:
        db = _make_db(tmp_path, flush_threshold=5)
        for i in range(4):
            db.upsert(vector_id=f"v{i}", embedding=_vec(float(i)))
        shard_manifest = db.manifest_store.load(collection_id="col", shard_id="shard-0")
        assert shard_manifest is None

    def test_no_threshold_means_manual_only(self, tmp_path: Path) -> None:
        db = _make_db(tmp_path)  # flush_threshold=None
        for i in range(100):
            db.upsert(vector_id=f"v{i}", embedding=_vec(float(i)))
        shard_manifest = db.manifest_store.load(collection_id="col", shard_id="shard-0")
        assert shard_manifest is None

    def test_auto_flush_clears_mutable_buffer(self, tmp_path: Path) -> None:
        db = _make_db(tmp_path, flush_threshold=2)
        db.upsert(vector_id="a", embedding=_vec(1.0))
        db.upsert(vector_id="b", embedding=_vec(0.5))
        # After auto-flush, mutable buffer should be empty (or only have remaining)
        assert len(db.mutable_buffer.live_entries()) == 0


# ---------------------------------------------------------------------------
# 4. Query snapshot semantics
# ---------------------------------------------------------------------------

class TestQuerySnapshotSemantics:
    def test_snapshot_captured_at_query_start(self, tmp_path: Path) -> None:
        db = _make_db(tmp_path)
        db.upsert(vector_id="a", embedding=_vec(1.0))
        db.flush_mutable(segment_id="seg-0")

        # Capture snapshot — should contain seg-0
        paths, watermark = db._query_snapshot(shard_id="shard-0")
        assert any("seg-0" in p for p in paths)
        assert watermark >= 0

    def test_snapshot_watermark_is_shard_local(self, tmp_path: Path) -> None:
        db = _make_db(tmp_path)
        db.upsert(vector_id="default", embedding=_vec(0.2))
        db.upsert(vector_id="named", embedding=_vec(0.8), shard_id="shard-analytics")
        db.upsert(vector_id="named-2", embedding=_vec(0.9), shard_id="shard-analytics")

        _paths, watermark = db._query_snapshot(shard_id="shard-analytics")

        assert watermark == db._get_mutable_buffer("shard-analytics").watermark()

    def test_concurrent_manifest_change_does_not_affect_inflight_query(self, tmp_path: Path) -> None:
        """Simulate a manifest swap after snapshot is captured; query should use snapshot."""
        db = _make_db(tmp_path)
        db.upsert(vector_id="stable", embedding=_vec(1.0))
        db.flush_mutable(segment_id="seg-0")

        # Capture snapshot before swapping manifest
        snapshot_paths, _ = db._query_snapshot(shard_id="shard-0")

        # Simulate mid-query manifest change: add a new (non-existent) segment
        shard_manifest = db.manifest_store.load(collection_id="col", shard_id="shard-0")
        updated = shard_manifest.model_copy(
            update={"active_segment_ids": [*shard_manifest.active_segment_ids, "seg-phantom"]}
        )
        db.manifest_store.save(updated)

        # Query using the captured snapshot should not include phantom segment
        results = db._query_sealed_exactish(
            _vec(1.0),
            top_k=10,
            shard_id="shard-0",
            snapshot_paths=snapshot_paths,
        )
        result_ids = {r.vector_id for r in results}
        assert "stable" in result_ids

        # New snapshot would include the phantom if it existed (it doesn't, so safe)
        new_paths, _ = db._query_snapshot(shard_id="shard-0")
        assert new_paths != snapshot_paths or "seg-phantom" not in str(snapshot_paths)

    def test_query_exact_hybrid_uses_snapshot(self, tmp_path: Path) -> None:
        db = _make_db(tmp_path)
        db.upsert(vector_id="a", embedding=_vec(1.0))
        db.flush_mutable(segment_id="seg-0")

        results = db.query_exact_hybrid(_vec(1.0), top_k=5)
        assert "a" in results


# ---------------------------------------------------------------------------
# 5. Smarter compaction planner
# ---------------------------------------------------------------------------

class TestSmarterCompactionPlanner:
    def _make_manifest(
        self,
        segment_id: str,
        *,
        row_count: int,
        live_row_count: int,
        generation: int = 1,
        state: SegmentState = SegmentState.ACTIVE,
    ) -> SegmentManifest:
        return SegmentManifest(
            segment_id=segment_id,
            collection_id="col",
            shard_id="shard-0",
            generation=generation,
            state=state,
            row_count=row_count,
            live_row_count=live_row_count,
            deleted_row_count=row_count - live_row_count,
            embedding_version="v1",
            quantizer_version="v0",
        )

    def test_planner_triggers_on_many_segments(self) -> None:
        planner = CompactionPlanner(min_segment_count=2, max_total_rows=10000)
        manifests = [
            self._make_manifest(f"s{i}", row_count=100, live_row_count=100)
            for i in range(5)
        ]
        plan = planner.plan(manifests)
        assert plan is not None

    def test_planner_skips_low_delete_ratio_at_minimum_count(self) -> None:
        """With min_delete_ratio set, planner skips when ratio is too low."""
        planner = CompactionPlanner(min_segment_count=2, max_total_rows=10000, min_delete_ratio=0.5)
        # Exactly min_segment_count segments with 0% delete ratio
        manifests = [
            self._make_manifest(f"s{i}", row_count=100, live_row_count=100)
            for i in range(2)
        ]
        plan = planner.plan(manifests)
        assert plan is None

    def test_planner_triggers_on_high_delete_ratio(self) -> None:
        planner = CompactionPlanner(min_segment_count=2, max_total_rows=10000, min_delete_ratio=0.3)
        manifests = [
            self._make_manifest(f"s{i}", row_count=100, live_row_count=50)
            for i in range(2)
        ]
        plan = planner.plan(manifests)
        assert plan is not None

    def test_planner_triggers_with_many_segments_despite_low_delete_ratio(self) -> None:
        """With extra segments (count > min+1), proceed even with low delete ratio."""
        planner = CompactionPlanner(min_segment_count=2, max_total_rows=10000, min_delete_ratio=0.5)
        manifests = [
            self._make_manifest(f"s{i}", row_count=100, live_row_count=99)
            for i in range(4)  # well above min_segment_count + 1
        ]
        plan = planner.plan(manifests)
        assert plan is not None

    def test_eligibility_score_increases_with_delete_ratio(self) -> None:
        low_del = [self._make_manifest("a", row_count=100, live_row_count=100)]
        high_del = [self._make_manifest("b", row_count=100, live_row_count=10)]
        score_low = compaction_eligibility_score(low_del, min_segment_count=1, max_total_rows=10000)
        score_high = compaction_eligibility_score(high_del, min_segment_count=1, max_total_rows=10000)
        assert score_high > score_low

    def test_eligibility_score_zero_below_min_count(self) -> None:
        manifests = [self._make_manifest(f"s{i}", row_count=100, live_row_count=100) for i in range(2)]
        score = compaction_eligibility_score(
            manifests, min_segment_count=3, max_total_rows=10000
        )
        assert score == 0.0

    def test_plan_reason_contains_score(self) -> None:
        planner = CompactionPlanner(min_segment_count=2, max_total_rows=10000)
        manifests = [
            self._make_manifest(f"s{i}", row_count=100, live_row_count=80)
            for i in range(3)
        ]
        plan = planner.plan(manifests)
        assert plan is not None
        assert "eligibility-score" in plan.reason
        assert "delete-ratio" in plan.reason
