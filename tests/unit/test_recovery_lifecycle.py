from pathlib import Path

from recalllayer.engine.showcase_db import ShowcaseLocalDatabase


def test_recover_after_single_flush_replays_only_post_flush_writes_under_target_contract(tmp_path: Path) -> None:
    db = ShowcaseLocalDatabase(collection_id="documents", root_dir=tmp_path)
    db.upsert(vector_id="a", embedding=[1.0, 0.0], metadata={"region": "us"})
    db.flush_mutable(segment_id="seg-1", generation=1)
    db.upsert(vector_id="b", embedding=[0.0, 1.0], metadata={"region": "ca"})

    recovered = ShowcaseLocalDatabase(collection_id="documents", root_dir=tmp_path)
    applied = recovered.recover()

    assert applied == 1
    live_ids = {entry.record.vector_id for entry in recovered.mutable_buffer.live_entries()}
    assert live_ids == {"b"}
    assert recovered.query_exact_hybrid([1.0, 0.0], top_k=2) == ["a", "b"]


def test_recover_after_repeated_flushes_replays_nothing_when_no_new_writes_exist_under_target_contract(tmp_path: Path) -> None:
    db = ShowcaseLocalDatabase(collection_id="documents", root_dir=tmp_path)
    db.upsert(vector_id="a", embedding=[1.0, 0.0], metadata={"region": "us"})
    db.flush_mutable(segment_id="seg-1", generation=1)
    db.upsert(vector_id="b", embedding=[0.0, 1.0], metadata={"region": "ca"})
    db.flush_mutable(segment_id="seg-2", generation=2)

    recovered = ShowcaseLocalDatabase(collection_id="documents", root_dir=tmp_path)
    applied = recovered.recover()

    assert applied == 0
    assert recovered.mutable_buffer.live_entries() == []
    assert recovered.query_exact_hybrid([1.0, 0.0], top_k=2) == ["a", "b"]


def test_recover_after_repeated_flushes_plus_new_write_replays_only_newer_tail_under_target_contract(tmp_path: Path) -> None:
    db = ShowcaseLocalDatabase(collection_id="documents", root_dir=tmp_path)
    db.upsert(vector_id="a", embedding=[1.0, 0.0], metadata={"region": "us"})
    db.flush_mutable(segment_id="seg-1", generation=1)
    db.upsert(vector_id="b", embedding=[0.0, 1.0], metadata={"region": "ca"})
    db.flush_mutable(segment_id="seg-2", generation=2)
    db.upsert(vector_id="c", embedding=[0.9, 0.1], metadata={"region": "us"})

    recovered = ShowcaseLocalDatabase(collection_id="documents", root_dir=tmp_path)
    applied = recovered.recover()

    assert applied == 1
    live_ids = {entry.record.vector_id for entry in recovered.mutable_buffer.live_entries()}
    assert live_ids == {"c"}
    assert recovered.query_exact_hybrid([1.0, 0.0], top_k=3) == ["a", "c", "b"]
