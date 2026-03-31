from pathlib import Path

from turboquant_db.engine.compaction_executor import CompactionExecutor
from turboquant_db.engine.compaction_planner import CompactionPlanner
from turboquant_db.engine.compactor import LocalSegmentCompactor
from turboquant_db.engine.local_db import LocalVectorDatabase
from turboquant_db.engine.manifest_store import ManifestStore
from turboquant_db.engine.segment_gc import execute_segment_garbage_collection, plan_segment_garbage_collection
from turboquant_db.engine.segment_manifest_store import SegmentManifestStore
from turboquant_db.model.manifest import SegmentManifest, SegmentState, ShardManifest


def _manifest(segment_id: str, state: SegmentState) -> SegmentManifest:
    return SegmentManifest(
        segment_id=segment_id,
        collection_id="documents",
        shard_id="shard-0",
        generation=1,
        state=state,
        embedding_version="embed-v1",
        quantizer_version="tq-v0",
    )


def test_plan_segment_garbage_collection_returns_only_retired_segments(tmp_path: Path) -> None:
    candidates = plan_segment_garbage_collection(
        manifests=[_manifest("seg-1", SegmentState.RETIRED), _manifest("seg-2", SegmentState.ACTIVE)],
        segments_root=tmp_path,
    )

    assert [candidate.segment_id for candidate in candidates] == ["seg-1"]
    assert candidates[0].segment_path == tmp_path / "documents" / "shard-0" / "seg-1.segment.jsonl"
    assert candidates[0].manifest_paths == [tmp_path / "documents" / "shard-0" / "seg-1.manifest.json"]


def test_execute_segment_garbage_collection_removes_existing_files(tmp_path: Path) -> None:
    candidates = plan_segment_garbage_collection(
        manifests=[_manifest("seg-1", SegmentState.RETIRED)],
        segments_root=tmp_path,
    )
    candidates[0].segment_path.parent.mkdir(parents=True, exist_ok=True)
    candidates[0].segment_path.write_text("segment", encoding="utf-8")
    candidates[0].manifest_paths[0].write_text("manifest", encoding="utf-8")

    result = execute_segment_garbage_collection(candidates)

    assert result.removed_segment_ids == ["seg-1"]
    assert not candidates[0].segment_path.exists()
    assert not candidates[0].manifest_paths[0].exists()


def test_collect_retired_segments_removes_only_retired_artifacts(tmp_path: Path) -> None:
    db = LocalVectorDatabase(collection_id="documents", root_dir=tmp_path)
    db.upsert(vector_id="a", embedding=[1.0, 0.0], metadata={"region": "us"})
    db.flush_mutable(segment_id="seg-1", generation=1)
    db.upsert(vector_id="b", embedding=[0.0, 1.0], metadata={"region": "ca"})
    db.flush_mutable(segment_id="seg-2", generation=2)
    ManifestStore(tmp_path / "manifests").save(
        ShardManifest(shard_id="shard-0", collection_id="documents", active_segment_ids=["seg-1", "seg-2"])
    )

    executor = CompactionExecutor(
        planner=CompactionPlanner(min_segment_count=2, max_total_rows=10),
        compactor=LocalSegmentCompactor(segments_root=tmp_path / "segments", manifests_root=tmp_path / "manifests"),
        manifest_store=ManifestStore(tmp_path / "manifests"),
        segment_manifest_store=SegmentManifestStore(tmp_path / "segment-manifests"),
    )
    result = executor.compact_shard(collection_id="documents", shard_id="shard-0", output_segment_id="seg-merged", generation=3)
    assert result is not None

    seg_root = tmp_path / "segments" / "documents" / "shard-0"
    manifest_root = tmp_path / "manifests" / "documents" / "shard-0"
    assert (seg_root / "seg-1.segment.jsonl").exists()
    assert (seg_root / "seg-2.segment.jsonl").exists()
    assert (seg_root / "seg-merged.segment.jsonl").exists()

    gc_result = db.collect_retired_segments()

    assert gc_result.candidate_segment_ids == ["seg-1", "seg-2"]
    assert gc_result.result.removed_segment_ids == ["seg-1", "seg-2"]
    assert not (seg_root / "seg-1.segment.jsonl").exists()
    assert not (seg_root / "seg-2.segment.jsonl").exists()
    assert (seg_root / "seg-merged.segment.jsonl").exists()
    assert not (manifest_root / "seg-1.manifest.json").exists()
    assert not (manifest_root / "seg-2.manifest.json").exists()
    assert (manifest_root / "seg-merged.manifest.json").exists()


def test_collect_retired_segments_removes_retired_manifests_from_both_storage_roots(tmp_path: Path) -> None:
    db = LocalVectorDatabase(collection_id="documents", root_dir=tmp_path)
    db.upsert(vector_id="a", embedding=[1.0, 0.0], metadata={"region": "us"})
    db.flush_mutable(segment_id="seg-1", generation=1)
    ManifestStore(tmp_path / "manifests").save(
        ShardManifest(shard_id="shard-0", collection_id="documents", active_segment_ids=["seg-1"])
    )

    retired_manifest = SegmentManifestStore(tmp_path / "segment-manifests").load(
        collection_id="documents", shard_id="shard-0", segment_id="seg-1"
    )
    assert retired_manifest is not None
    SegmentManifestStore(tmp_path / "segment-manifests").save(retired_manifest.model_copy(update={"state": SegmentState.RETIRED}))

    compacted_manifest_path = tmp_path / "manifests" / "documents" / "shard-0" / "seg-1.manifest.json"
    compacted_manifest_path.parent.mkdir(parents=True, exist_ok=True)
    compacted_manifest_path.write_text("retired-compact-manifest", encoding="utf-8")

    gc_result = db.collect_retired_segments()

    assert gc_result.candidate_segment_ids == ["seg-1"]
    assert not (tmp_path / "segments" / "documents" / "shard-0" / "seg-1.segment.jsonl").exists()
    assert not (tmp_path / "segments" / "documents" / "shard-0" / "seg-1.manifest.json").exists()
    assert not compacted_manifest_path.exists()


def test_collect_retired_segments_is_idempotent(tmp_path: Path) -> None:
    db = LocalVectorDatabase(collection_id="documents", root_dir=tmp_path)
    db.upsert(vector_id="a", embedding=[1.0, 0.0], metadata={"region": "us"})
    db.flush_mutable(segment_id="seg-1", generation=1)
    db.upsert(vector_id="b", embedding=[0.0, 1.0], metadata={"region": "ca"})
    db.flush_mutable(segment_id="seg-2", generation=2)
    ManifestStore(tmp_path / "manifests").save(
        ShardManifest(shard_id="shard-0", collection_id="documents", active_segment_ids=["seg-1", "seg-2"])
    )

    executor = CompactionExecutor(
        planner=CompactionPlanner(min_segment_count=2, max_total_rows=10),
        compactor=LocalSegmentCompactor(segments_root=tmp_path / "segments", manifests_root=tmp_path / "manifests"),
        manifest_store=ManifestStore(tmp_path / "manifests"),
        segment_manifest_store=SegmentManifestStore(tmp_path / "segment-manifests"),
    )
    assert executor.compact_shard(collection_id="documents", shard_id="shard-0", output_segment_id="seg-merged", generation=3) is not None

    first = db.collect_retired_segments()
    second = db.collect_retired_segments()

    assert first.result.removed_segment_ids == ["seg-1", "seg-2"]
    assert second.result.removed_segment_ids == ["seg-1", "seg-2"]
    assert second.result.removed_paths == []
