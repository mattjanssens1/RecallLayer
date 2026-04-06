from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from recalllayer.engine.compaction_executor import CompactionExecutor
from recalllayer.engine.compaction_planner import CompactionPlanner
from recalllayer.engine.compactor import LocalSegmentCompactor
from recalllayer.engine.local_db import LocalVectorDatabase
from recalllayer.engine.manifest_store import ManifestStore
from recalllayer.engine.segment_manifest_store import SegmentManifestStore
from recalllayer.engine.showcase_db import ShowcaseLocalDatabase
from recalllayer.engine.write_log import DurabilityMode


def _build_executor(tmp_path: Path) -> CompactionExecutor:
    return CompactionExecutor(
        planner=CompactionPlanner(min_segment_count=2, max_total_rows=1000, min_delete_ratio=0.0),
        compactor=LocalSegmentCompactor(
            segments_root=tmp_path / "segments",
            manifests_root=tmp_path / "manifests",
        ),
        manifest_store=ManifestStore(tmp_path / "manifests"),
        segment_manifest_store=SegmentManifestStore(tmp_path / "segment-manifests"),
    )


def test_concurrent_upserts_and_deletes_recover_to_consistent_latest_state(tmp_path: Path) -> None:
    db = LocalVectorDatabase(
        collection_id="documents",
        root_dir=tmp_path,
        durability_mode=DurabilityMode.LOG_SYNC,
    )

    def worker(index: int) -> None:
        vector_id = f"vec-{index % 8}"
        db.upsert(vector_id=vector_id, embedding=[float(index), float(index + 1)], metadata={"i": index})
        if index % 3 == 0:
            db.delete(vector_id=vector_id)

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(worker, range(40)))

    recovered = LocalVectorDatabase(
        collection_id="documents",
        root_dir=tmp_path,
        durability_mode=DurabilityMode.LOG_SYNC,
    )
    applied = recovered.recover()

    assert applied >= 40
    assert recovered.mutable_buffer.watermark() == db.mutable_buffer.watermark()
    for idx in range(8):
        entry = recovered.mutable_buffer.get(f"vec-{idx}")
        assert entry is not None


def test_recover_after_flush_manifest_save_failure_replays_tail_only(tmp_path: Path, monkeypatch) -> None:
    db = ShowcaseLocalDatabase(
        collection_id="documents",
        root_dir=tmp_path,
        durability_mode=DurabilityMode.LOG_SYNC,
    )
    db.upsert(vector_id="a", embedding=[1.0, 0.0], metadata={})

    original_save = db.manifest_store.save
    call_count = {"n": 0}

    def flaky_save(manifest):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise RuntimeError("simulated crash during manifest save")
        return original_save(manifest)

    monkeypatch.setattr(db.manifest_store, "save", flaky_save)

    with pytest.raises(RuntimeError):
        db.flush_mutable(segment_id="seg-1", generation=1)

    recovered = ShowcaseLocalDatabase(
        collection_id="documents",
        root_dir=tmp_path,
        durability_mode=DurabilityMode.LOG_SYNC,
    )
    applied = recovered.recover()

    assert applied == 1
    assert recovered.mutable_buffer.get("a") is not None


def test_recover_after_compaction_manifest_failure_preserves_old_segments(tmp_path: Path, monkeypatch) -> None:
    db = ShowcaseLocalDatabase(
        collection_id="documents",
        root_dir=tmp_path,
        durability_mode=DurabilityMode.LOG_SYNC,
    )
    db.upsert(vector_id="a", embedding=[1.0, 0.0], metadata={})
    db.flush_mutable(segment_id="seg-1", generation=1)
    db.upsert(vector_id="b", embedding=[0.0, 1.0], metadata={})
    db.flush_mutable(segment_id="seg-2", generation=2)

    executor = _build_executor(tmp_path)
    original_save = executor.manifest_store.save
    call_count = {"n": 0}

    def flaky_save(manifest):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise RuntimeError("simulated crash during shard manifest update")
        return original_save(manifest)

    monkeypatch.setattr(executor.manifest_store, "save", flaky_save)

    with pytest.raises(RuntimeError):
        executor.compact_shard(
            collection_id="documents",
            shard_id="shard-0",
            output_segment_id="seg-merged",
            generation=3,
        )

    recovered = ShowcaseLocalDatabase(
        collection_id="documents",
        root_dir=tmp_path,
        durability_mode=DurabilityMode.LOG_SYNC,
    )
    applied = recovered.recover()

    assert applied == 0
    results = recovered.query_exact_hybrid([1.0, 0.0], top_k=2)
    assert results == ["a", "b"]


def test_recovery_after_partial_maintenance_and_new_tail_write(tmp_path: Path) -> None:
    db = ShowcaseLocalDatabase(
        collection_id="documents",
        root_dir=tmp_path,
        durability_mode=DurabilityMode.LOG_SYNC,
    )
    db.upsert(vector_id="a", embedding=[1.0, 0.0], metadata={})
    db.flush_mutable(segment_id="seg-1", generation=1)
    db.upsert(vector_id="b", embedding=[0.0, 1.0], metadata={})
    db.flush_mutable(segment_id="seg-2", generation=2)

    executor = _build_executor(tmp_path)
    result = executor.compact_shard(
        collection_id="documents",
        shard_id="shard-0",
        output_segment_id="seg-merged",
        generation=3,
    )
    assert result is not None

    db.upsert(vector_id="c", embedding=[0.9, 0.1], metadata={})

    recovered = ShowcaseLocalDatabase(
        collection_id="documents",
        root_dir=tmp_path,
        durability_mode=DurabilityMode.LOG_SYNC,
    )
    applied = recovered.recover()

    assert applied == 1
    assert recovered.query_exact_hybrid([1.0, 0.0], top_k=3) == ["a", "c", "b"]


def test_recovery_preserves_tail_writes_even_before_shard_partitioned_mutable_replay(tmp_path: Path) -> None:
    db = ShowcaseLocalDatabase(
        collection_id="documents",
        root_dir=tmp_path,
        durability_mode=DurabilityMode.LOG_SYNC,
    )
    db.upsert(vector_id="a", embedding=[1.0, 0.0], metadata={}, shard_id="shard-0")
    db.flush_mutable(shard_id="shard-0", segment_id="seg-a", generation=1)
    db.upsert(vector_id="b", embedding=[0.0, 1.0], metadata={}, shard_id="shard-1")
    db.flush_mutable(shard_id="shard-1", segment_id="seg-b", generation=1)
    db.upsert(vector_id="tail-a", embedding=[0.8, 0.2], metadata={}, shard_id="shard-0")
    db.upsert(vector_id="tail-b", embedding=[0.2, 0.8], metadata={}, shard_id="shard-1")

    recovered = ShowcaseLocalDatabase(
        collection_id="documents",
        root_dir=tmp_path,
        durability_mode=DurabilityMode.LOG_SYNC,
    )
    applied = recovered.recover()

    assert applied == 3
    assert recovered.query_exact_hybrid([1.0, 0.0], top_k=3, shard_id="shard-0")[:2] == ["a", "tail-a"]
    assert recovered.query_exact_hybrid([0.0, 1.0], top_k=3, shard_id="shard-1")[:1] == ["b"]
    assert {entry.record.vector_id for entry in recovered.mutable_buffer.live_entries()} >= {"tail-a", "tail-b"}
