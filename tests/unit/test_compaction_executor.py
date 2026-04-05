from pathlib import Path

from recalllayer.engine.compaction_executor import CompactionExecutor
from recalllayer.engine.compaction_planner import CompactionPlanner
from recalllayer.engine.compactor import LocalSegmentCompactor
from recalllayer.engine.local_db import LocalVectorDatabase
from recalllayer.engine.manifest_store import ManifestStore
from recalllayer.engine.segment_manifest_store import SegmentManifestStore
from recalllayer.engine.showcase_db import ShowcaseLocalDatabase
from recalllayer.model.manifest import SegmentState, ShardManifest


def test_compaction_executor_retires_sources_and_updates_active_segments(tmp_path: Path) -> None:
    db = LocalVectorDatabase(collection_id='documents', root_dir=tmp_path)
    db.upsert(vector_id='a', embedding=[1.0, 0.0], metadata={'region': 'us'})
    db.flush_mutable(segment_id='seg-1', generation=1)
    db.upsert(vector_id='b', embedding=[0.0, 1.0], metadata={'region': 'ca'})
    db.flush_mutable(segment_id='seg-2', generation=2)
    ManifestStore(tmp_path / 'manifests').save(
        ShardManifest(shard_id='shard-0', collection_id='documents', active_segment_ids=['seg-1', 'seg-2'])
    )

    executor = CompactionExecutor(
        planner=CompactionPlanner(min_segment_count=2, max_total_rows=10),
        compactor=LocalSegmentCompactor(segments_root=tmp_path / 'segments', manifests_root=tmp_path / 'manifests'),
        manifest_store=ManifestStore(tmp_path / 'manifests'),
        segment_manifest_store=SegmentManifestStore(tmp_path / 'segment-manifests'),
    )

    result = executor.compact_shard(
        collection_id='documents',
        shard_id='shard-0',
        output_segment_id='seg-merged',
        generation=3,
    )

    assert result is not None
    assert result.updated_shard_manifest.active_segment_ids == ['seg-merged']
    assert result.selected_source_segment_ids == ['seg-1', 'seg-2']
    states = {manifest.segment_id: manifest.state for manifest in result.updated_segment_manifests}
    assert states['seg-1'] == SegmentState.RETIRED
    assert states['seg-2'] == SegmentState.RETIRED
    assert states['seg-merged'] == SegmentState.ACTIVE

    stored_shard = ManifestStore(tmp_path / 'manifests').load(collection_id='documents', shard_id='shard-0')
    assert stored_shard is not None
    assert stored_shard.active_segment_ids == ['seg-merged']

    stored_segment_manifests = SegmentManifestStore(tmp_path / 'segment-manifests').list_manifests(
        collection_id='documents', shard_id='shard-0'
    )
    stored_states = {manifest.segment_id: manifest.state for manifest in stored_segment_manifests}
    assert stored_states == {
        'seg-1': SegmentState.RETIRED,
        'seg-2': SegmentState.RETIRED,
        'seg-merged': SegmentState.ACTIVE,
    }


def test_compaction_executor_returns_none_when_not_enough_candidates(tmp_path: Path) -> None:
    db = LocalVectorDatabase(collection_id='documents', root_dir=tmp_path)
    db.upsert(vector_id='a', embedding=[1.0, 0.0], metadata={'region': 'us'})
    db.flush_mutable(segment_id='seg-1', generation=1)

    executor = CompactionExecutor(
        planner=CompactionPlanner(min_segment_count=2, max_total_rows=10),
        compactor=LocalSegmentCompactor(segments_root=tmp_path / 'segments', manifests_root=tmp_path / 'manifests'),
        manifest_store=ManifestStore(tmp_path / 'manifests'),
        segment_manifest_store=SegmentManifestStore(tmp_path / 'segment-manifests'),
    )

    result = executor.compact_shard(collection_id='documents', shard_id='shard-0', output_segment_id='seg-merged', generation=2)

    assert result is None


def test_post_compaction_queries_use_new_active_segment_set(tmp_path: Path) -> None:
    db = ShowcaseLocalDatabase(collection_id='documents', root_dir=tmp_path)
    db.upsert(vector_id='a', embedding=[1.0, 0.0], metadata={'region': 'us'})
    db.flush_mutable(segment_id='seg-1', generation=1)
    db.upsert(vector_id='b', embedding=[0.0, 1.0], metadata={'region': 'ca'})
    db.flush_mutable(segment_id='seg-2', generation=2)
    ManifestStore(tmp_path / 'manifests').save(
        ShardManifest(shard_id='shard-0', collection_id='documents', active_segment_ids=['seg-1', 'seg-2'])
    )

    executor = CompactionExecutor(
        planner=CompactionPlanner(min_segment_count=2, max_total_rows=10),
        compactor=LocalSegmentCompactor(segments_root=tmp_path / 'segments', manifests_root=tmp_path / 'manifests'),
        manifest_store=ManifestStore(tmp_path / 'manifests'),
        segment_manifest_store=SegmentManifestStore(tmp_path / 'segment-manifests'),
    )
    result = executor.compact_shard(
        collection_id='documents',
        shard_id='shard-0',
        output_segment_id='seg-merged',
        generation=3,
    )

    assert result is not None
    assert db.query_exact_hybrid([1.0, 0.0], top_k=2)[:2] == ['a', 'b']
