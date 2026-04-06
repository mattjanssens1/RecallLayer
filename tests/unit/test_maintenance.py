from __future__ import annotations

from pathlib import Path

from recalllayer.engine.compaction_executor import CompactionExecutor
from recalllayer.engine.compaction_planner import CompactionPlanner
from recalllayer.engine.compactor import LocalSegmentCompactor
from recalllayer.engine.local_db import LocalVectorDatabase
from recalllayer.engine.maintenance import (
    AdaptiveMaintenancePlanner,
    AdaptiveMaintenancePolicy,
    MaintenanceCandidate,
    MaintenanceThresholds,
)


def _make_executor(db: LocalVectorDatabase, tmp_path: Path) -> CompactionExecutor:
    return CompactionExecutor(
        planner=CompactionPlanner(min_segment_count=2, max_total_rows=1000, min_delete_ratio=0.0, delete_ratio_weight=3.0),
        compactor=LocalSegmentCompactor(
            segments_root=tmp_path / "segments",
            manifests_root=tmp_path / "manifests",
        ),
        manifest_store=db.manifest_store,
        segment_manifest_store=db.segment_manifest_store,
    )


def test_adaptive_planner_ranks_higher_delete_pressure_first() -> None:
    planner = AdaptiveMaintenancePlanner(
        thresholds=MaintenanceThresholds(min_segment_count=2, min_delete_ratio=0.05, max_total_rows=100)
    )
    candidates = [
        planner.score_shard(
            shard_id="shard-calm",
            segment_count=2,
            total_rows=40,
            live_rows=38,
            mutable_rows=0,
        ),
        planner.score_shard(
            shard_id="shard-hot",
            segment_count=4,
            total_rows=95,
            live_rows=35,
            mutable_rows=20,
        ),
    ]

    ranked = planner.rank_candidates(candidates)

    assert ranked
    assert ranked[0].shard_id == "shard-hot"
    assert ranked[0].score > candidates[0].score


def test_adaptive_policy_compacts_best_ranked_shard(tmp_path: Path) -> None:
    db = LocalVectorDatabase(collection_id="documents", root_dir=tmp_path)

    # shard-0: modest pressure
    db.upsert(vector_id="a1", embedding=[1.0, 0.0], shard_id="shard-0")
    db.flush_mutable(shard_id="shard-0", segment_id="seg-0a", generation=1)
    db.upsert(vector_id="a2", embedding=[0.9, 0.1], shard_id="shard-0")
    db.flush_mutable(shard_id="shard-0", segment_id="seg-0b", generation=2)

    # shard-1: more fragmentation + deletes
    db.upsert(vector_id="b1", embedding=[0.0, 1.0], shard_id="shard-1")
    db.flush_mutable(shard_id="shard-1", segment_id="seg-1a", generation=1)
    db.upsert(vector_id="b2", embedding=[0.1, 0.9], shard_id="shard-1")
    db.flush_mutable(shard_id="shard-1", segment_id="seg-1b", generation=2)
    db.upsert(vector_id="b3", embedding=[0.2, 0.8], shard_id="shard-1")
    db.flush_mutable(shard_id="shard-1", segment_id="seg-1c", generation=3)
    db.upsert(vector_id="b4", embedding=[0.3, 0.7], shard_id="shard-1")
    db.flush_mutable(shard_id="shard-1", segment_id="seg-1d", generation=4)

    executor = _make_executor(db, tmp_path)
    policy = AdaptiveMaintenancePolicy(
        executor=executor,
        mutable_buffer_provider=lambda shard_id: len(db._get_mutable_buffer(shard_id).all_entries()),
    )

    result = policy.maybe_compact_best(collection_id="documents", generation=5)

    assert result is not None
    assert result.updated_shard_manifest.shard_id == "shard-1"
    assert any(seg.startswith("seg-maintained-shard-1") for seg in result.updated_shard_manifest.active_segment_ids)


def test_adaptive_policy_returns_none_when_nothing_qualifies(tmp_path: Path) -> None:
    db = LocalVectorDatabase(collection_id="documents", root_dir=tmp_path)
    db.upsert(vector_id="a", embedding=[1.0, 0.0], shard_id="shard-0")
    db.flush_mutable(shard_id="shard-0", segment_id="seg-1", generation=1)

    executor = _make_executor(db, tmp_path)
    policy = AdaptiveMaintenancePolicy(executor=executor)

    result = policy.maybe_compact_best(collection_id="documents", generation=2)

    assert result is None
