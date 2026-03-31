from pathlib import Path

from turboquant_db.engine.compaction_executor import CompactionExecutor
from turboquant_db.engine.compaction_planner import CompactionPlanner
from turboquant_db.engine.compactor import LocalSegmentCompactor
from turboquant_db.engine.local_db import LocalVectorDatabase
from turboquant_db.engine.manifest_store import ManifestStore
from turboquant_db.engine.segment_manifest_store import SegmentManifestStore
from turboquant_db.model.manifest import SegmentState


def test_compaction_executor_updates_manifests_and_retires_sources(tmp_path: Path) -> None:
    db = LocalVectorDatabase(collection_id='documents', root_dir=tmp_path)
    db.upsert(vector_id='a', embedding=[1.0, 0.0], metadata={'region': 'us'})
    db.flush_mutable(segment_id='seg-1', generation=1)
    db.upsert(vector_id='b', embedding=[0.0, 1.0], metadata={'region': 'ca'})
    db.flush_mutable(segment_id='seg-2', generation=2)

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
    states = {manifest.segment_id: manifest.state for manifest in result.updated_segment_manifests}
    assert states['seg-1'] == SegmentState.RETIRED
    assert states['seg-2'] == SegmentState.RETIRED
    assert states['seg-merged'] == SegmentState.ACTIVE
