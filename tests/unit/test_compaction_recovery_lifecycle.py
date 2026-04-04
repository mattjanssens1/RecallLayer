from pathlib import Path

from turboquant_db.engine.compaction_executor import CompactionExecutor
from turboquant_db.engine.compaction_planner import CompactionPlanner
from turboquant_db.engine.compactor import LocalSegmentCompactor
from turboquant_db.engine.manifest_store import ManifestStore
from turboquant_db.engine.segment_manifest_store import SegmentManifestStore
from turboquant_db.engine.showcase_db import ShowcaseLocalDatabase


def build_executor(tmp_path: Path) -> CompactionExecutor:
    return CompactionExecutor(
        planner=CompactionPlanner(min_segment_count=2, max_total_rows=10),
        compactor=LocalSegmentCompactor(segments_root=tmp_path / 'segments', manifests_root=tmp_path / 'manifests'),
        manifest_store=ManifestStore(tmp_path / 'manifests'),
        segment_manifest_store=SegmentManifestStore(tmp_path / 'segment-manifests'),
    )


def test_compaction_keeps_replay_watermark_aligned_and_monotonic(tmp_path: Path) -> None:
    db = ShowcaseLocalDatabase(collection_id='documents', root_dir=tmp_path)
    db.upsert(vector_id='a', embedding=[1.0, 0.0], metadata={'region': 'us'})
    first_manifest = db.flush_mutable(segment_id='seg-1', generation=1)
    db.upsert(vector_id='b', embedding=[0.0, 1.0], metadata={'region': 'ca'})
    second_manifest = db.flush_mutable(segment_id='seg-2', generation=2)

    assert first_manifest is not None
    assert second_manifest is not None
    assert second_manifest.replay_from_write_epoch == 2

    executor = build_executor(tmp_path)
    result = executor.compact_shard(collection_id='documents', shard_id='shard-0', output_segment_id='seg-merged', generation=3)

    assert result is not None
    assert result.updated_shard_manifest.replay_from_write_epoch == 2

    stored_shard = ManifestStore(tmp_path / 'manifests').load(collection_id='documents', shard_id='shard-0')
    assert stored_shard is not None
    assert stored_shard.replay_from_write_epoch == 2


def test_compaction_does_not_move_replay_watermark_backwards_when_only_older_segments_are_compacted(tmp_path: Path) -> None:
    db = ShowcaseLocalDatabase(collection_id='documents', root_dir=tmp_path)
    db.upsert(vector_id='a', embedding=[1.0, 0.0], metadata={'region': 'us'})
    db.flush_mutable(segment_id='seg-1', generation=1)
    db.upsert(vector_id='b', embedding=[0.0, 1.0], metadata={'region': 'ca'})
    latest_manifest = db.flush_mutable(segment_id='seg-2', generation=2)

    assert latest_manifest is not None
    assert latest_manifest.replay_from_write_epoch == 2

    executor = build_executor(tmp_path)
    result = executor.compact_shard(
        collection_id='documents',
        shard_id='shard-0',
        output_segment_id='seg-merged',
        generation=3,
    )

    assert result is not None
    assert result.updated_shard_manifest.replay_from_write_epoch >= latest_manifest.replay_from_write_epoch


def test_recover_after_compaction_replays_nothing_when_no_new_writes_exist(tmp_path: Path) -> None:
    db = ShowcaseLocalDatabase(collection_id='documents', root_dir=tmp_path)
    db.upsert(vector_id='a', embedding=[1.0, 0.0], metadata={'region': 'us'})
    db.flush_mutable(segment_id='seg-1', generation=1)
    db.upsert(vector_id='b', embedding=[0.0, 1.0], metadata={'region': 'ca'})
    db.flush_mutable(segment_id='seg-2', generation=2)

    executor = build_executor(tmp_path)
    result = executor.compact_shard(collection_id='documents', shard_id='shard-0', output_segment_id='seg-merged', generation=3)
    assert result is not None

    recovered = ShowcaseLocalDatabase(collection_id='documents', root_dir=tmp_path)
    applied = recovered.recover()

    assert applied == 0
    assert recovered.mutable_buffer.live_entries() == []
    assert recovered.query_exact_hybrid([1.0, 0.0], top_k=2) == ['a', 'b']


def test_recover_after_compaction_plus_new_write_replays_only_newer_tail(tmp_path: Path) -> None:
    db = ShowcaseLocalDatabase(collection_id='documents', root_dir=tmp_path)
    db.upsert(vector_id='a', embedding=[1.0, 0.0], metadata={'region': 'us'})
    db.flush_mutable(segment_id='seg-1', generation=1)
    db.upsert(vector_id='b', embedding=[0.0, 1.0], metadata={'region': 'ca'})
    db.flush_mutable(segment_id='seg-2', generation=2)

    executor = build_executor(tmp_path)
    result = executor.compact_shard(collection_id='documents', shard_id='shard-0', output_segment_id='seg-merged', generation=3)
    assert result is not None

    db.upsert(vector_id='c', embedding=[0.9, 0.1], metadata={'region': 'us'})

    recovered = ShowcaseLocalDatabase(collection_id='documents', root_dir=tmp_path)
    applied = recovered.recover()

    assert applied == 1
    live_ids = {entry.record.vector_id for entry in recovered.mutable_buffer.live_entries()}
    assert live_ids == {'c'}
    assert recovered.query_exact_hybrid([1.0, 0.0], top_k=3) == ['a', 'c', 'b']
