from pathlib import Path

from recalllayer.engine.local_db import LocalVectorDatabase


def test_local_db_upsert_query_flush_and_recover(tmp_path: Path) -> None:
    db = LocalVectorDatabase(collection_id="documents", root_dir=tmp_path)
    db.upsert(vector_id="a", embedding=[1.0, 0.0], metadata={"region": "us"})
    db.upsert(vector_id="b", embedding=[0.0, 1.0], metadata={"region": "ca"})

    assert db.query_exact([0.9, 0.1], top_k=1) == ["a"]
    assert db.query_compressed([0.9, 0.1], top_k=1) == ["a"]

    manifest = db.flush_mutable(segment_id="seg-1", generation=1)
    assert manifest.active_segment_ids == ["seg-1"]

    loaded_shard, loaded_segments = db.load_manifest_set()
    assert loaded_shard is not None
    assert loaded_shard.active_segment_ids == ["seg-1"]
    assert [segment.segment_id for segment in loaded_segments] == ["seg-1"]
    assert loaded_segments[0].state.value == "active"

    recovered = LocalVectorDatabase(collection_id="documents", root_dir=tmp_path)
    applied = recovered.recover()
    assert applied == 0
    assert recovered.mutable_buffer.live_entries() == []
