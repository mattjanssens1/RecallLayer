from pathlib import Path

from recalllayer.engine.compaction_executor import CompactionExecutor
from recalllayer.engine.compaction_planner import CompactionPlanner
from recalllayer.engine.compactor import LocalSegmentCompactor
from recalllayer.engine.manifest_store import ManifestStore
from recalllayer.engine.segment_manifest_store import SegmentManifestStore
from recalllayer.engine.showcase_db import ShowcaseLocalDatabase


def build_executor(tmp_path: Path) -> CompactionExecutor:
    return CompactionExecutor(
        planner=CompactionPlanner(min_segment_count=2, max_total_rows=10),
        compactor=LocalSegmentCompactor(segments_root=tmp_path / 'segments', manifests_root=tmp_path / 'manifests'),
        manifest_store=ManifestStore(tmp_path / 'manifests'),
        segment_manifest_store=SegmentManifestStore(tmp_path / 'segment-manifests'),
    )


def test_delete_after_flush_masks_sealed_row_before_restart(tmp_path: Path) -> None:
    db = ShowcaseLocalDatabase(collection_id='documents', root_dir=tmp_path)
    db.upsert(vector_id='a', embedding=[1.0, 0.0], metadata={'region': 'us'})
    db.flush_mutable(segment_id='seg-1', generation=1)

    db.delete(vector_id='a')

    assert db.query_exact_hybrid([1.0, 0.0], top_k=1) == []
    assert db.query_compressed_hybrid([1.0, 0.0], top_k=1) == []


def test_delete_after_flush_masks_sealed_row_after_restart(tmp_path: Path) -> None:
    db = ShowcaseLocalDatabase(collection_id='documents', root_dir=tmp_path)
    db.upsert(vector_id='a', embedding=[1.0, 0.0], metadata={'region': 'us'})
    db.flush_mutable(segment_id='seg-1', generation=1)
    db.delete(vector_id='a')

    recovered = ShowcaseLocalDatabase(collection_id='documents', root_dir=tmp_path)
    recovered.recover()

    assert recovered.query_exact_hybrid([1.0, 0.0], top_k=1) == []
    assert recovered.query_compressed_hybrid([1.0, 0.0], top_k=1) == []


def test_delete_then_reupsert_same_id_follows_latest_write_wins(tmp_path: Path) -> None:
    db = ShowcaseLocalDatabase(collection_id='documents', root_dir=tmp_path)
    db.upsert(vector_id='a', embedding=[1.0, 0.0], metadata={'version': 'old'})
    db.flush_mutable(segment_id='seg-1', generation=1)
    db.delete(vector_id='a')
    db.upsert(vector_id='a', embedding=[0.9, 0.1], metadata={'version': 'new'})

    assert db.query_exact_hybrid([1.0, 0.0], top_k=1) == ['a']
    assert db.query_compressed_hybrid([1.0, 0.0], top_k=1) == ['a']


def test_tombstone_masking_still_holds_after_compaction_and_restart(tmp_path: Path) -> None:
    db = ShowcaseLocalDatabase(collection_id='documents', root_dir=tmp_path)
    db.upsert(vector_id='a', embedding=[1.0, 0.0], metadata={'region': 'us'})
    db.flush_mutable(segment_id='seg-1', generation=1)
    db.upsert(vector_id='b', embedding=[0.0, 1.0], metadata={'region': 'ca'})
    db.flush_mutable(segment_id='seg-2', generation=2)

    executor = build_executor(tmp_path)
    result = executor.compact_shard(collection_id='documents', shard_id='shard-0', output_segment_id='seg-merged', generation=3)
    assert result is not None

    db.delete(vector_id='a')

    recovered = ShowcaseLocalDatabase(collection_id='documents', root_dir=tmp_path)
    recovered.recover()

    assert recovered.query_exact_hybrid([1.0, 0.0], top_k=2) == ['b']
