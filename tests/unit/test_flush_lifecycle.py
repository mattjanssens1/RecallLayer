from pathlib import Path

from recalllayer.engine.showcase_db import ShowcaseLocalDatabase
from recalllayer.model.manifest import SegmentState


def test_flush_current_contract_creates_active_segment_and_preserves_write_epoch_bounds(tmp_path: Path) -> None:
    db = ShowcaseLocalDatabase(collection_id="documents", root_dir=tmp_path)
    db.upsert(vector_id="a", embedding=[1.0, 0.0], metadata={"region": "us"})
    db.upsert(vector_id="b", embedding=[0.0, 1.0], metadata={"region": "ca"})

    shard_manifest = db.flush_mutable(segment_id="seg-2", generation=7)
    loaded_shard, segment_manifests = db.load_manifest_set()

    assert shard_manifest is not None
    assert shard_manifest.active_segment_ids == ["seg-2"]
    assert loaded_shard is not None
    assert loaded_shard.active_segment_ids == ["seg-2"]

    assert [manifest.segment_id for manifest in segment_manifests] == ["seg-2"]
    segment_manifest = segment_manifests[0]
    assert segment_manifest.state == SegmentState.ACTIVE
    assert segment_manifest.generation == 7
    assert segment_manifest.row_count == 2
    assert segment_manifest.live_row_count == 2
    assert segment_manifest.deleted_row_count == 0
    assert segment_manifest.min_write_epoch == 1
    assert segment_manifest.max_write_epoch == 2

    results = db.query_exact_hybrid([1.0, 0.0], top_k=2)
    assert results[0] == "a"
    assert set(results) == {"a", "b"}


def test_second_flush_adds_new_active_segment_and_preserves_prior_query_visibility(tmp_path: Path) -> None:
    db = ShowcaseLocalDatabase(collection_id="documents", root_dir=tmp_path)
    db.upsert(vector_id="a", embedding=[1.0, 0.0], metadata={"region": "us"})
    first_manifest = db.flush_mutable(segment_id="seg-1", generation=1)

    db.upsert(vector_id="b", embedding=[0.0, 1.0], metadata={"region": "ca"})
    second_manifest = db.flush_mutable(segment_id="seg-2", generation=2)
    loaded_shard, segment_manifests = db.load_manifest_set()

    assert first_manifest is not None
    assert second_manifest is not None
    assert first_manifest.active_segment_ids == ["seg-1"]
    assert second_manifest.active_segment_ids == ["seg-1", "seg-2"]
    assert loaded_shard is not None
    assert loaded_shard.active_segment_ids == ["seg-1", "seg-2"]
    assert [manifest.segment_id for manifest in segment_manifests] == ["seg-1", "seg-2"]

    assert db.mutable_buffer.live_entries() == []
    results = db.query_exact_hybrid([1.0, 0.0], top_k=2)
    assert results == ["a", "b"]
