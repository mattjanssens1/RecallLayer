from __future__ import annotations

from pathlib import Path

from recalllayer.engine.showcase_db import ShowcaseLocalDatabase
from recalllayer.engine.write_log import WriteLog


def test_write_log_persists_shard_id_and_can_filter_by_shard(tmp_path: Path) -> None:
    log = WriteLog(tmp_path / "writes.jsonl")
    log.append_upsert(
        collection_id="documents",
        vector_id="a",
        shard_id="shard-0",
        write_epoch=1,
        embedding=[1.0, 0.0],
        metadata={},
    )
    log.append_upsert(
        collection_id="documents",
        vector_id="b",
        shard_id="shard-1",
        write_epoch=2,
        embedding=[0.0, 1.0],
        metadata={},
    )

    shard0 = list(log.replay(shard_id="shard-0"))
    shard1 = list(log.replay(shard_id="shard-1"))

    assert [entry.vector_id for entry in shard0] == ["a"]
    assert [entry.vector_id for entry in shard1] == ["b"]


def test_recover_targets_only_requested_shard_tail(tmp_path: Path) -> None:
    db = ShowcaseLocalDatabase(collection_id="documents", root_dir=tmp_path)
    db.upsert(vector_id="a", embedding=[1.0, 0.0], metadata={}, shard_id="shard-0")
    db.flush_mutable(shard_id="shard-0", segment_id="seg-a", generation=1)
    db.upsert(vector_id="b", embedding=[0.0, 1.0], metadata={}, shard_id="shard-1")
    db.flush_mutable(shard_id="shard-1", segment_id="seg-b", generation=1)
    db.upsert(vector_id="tail-a", embedding=[0.8, 0.2], metadata={}, shard_id="shard-0")
    db.upsert(vector_id="tail-b", embedding=[0.2, 0.8], metadata={}, shard_id="shard-1")

    recovered = ShowcaseLocalDatabase(collection_id="documents", root_dir=tmp_path)
    applied = recovered.recover(shard_id="shard-0")

    assert applied == 1
    assert recovered.query_exact_hybrid([1.0, 0.0], top_k=3, shard_id="shard-0")[:2] == ["a", "tail-a"]
    assert recovered.query_exact_hybrid([0.0, 1.0], top_k=3, shard_id="shard-1") == ["b"]
    assert {entry.record.vector_id for entry in recovered._get_mutable_buffer("shard-0").live_entries()} == {"tail-a"}
    assert recovered._get_mutable_buffer("shard-1").live_entries() == []


def test_recover_all_shards_via_separate_calls_rebuilds_both_tails(tmp_path: Path) -> None:
    db = ShowcaseLocalDatabase(collection_id="documents", root_dir=tmp_path)
    db.upsert(vector_id="a", embedding=[1.0, 0.0], metadata={}, shard_id="shard-0")
    db.flush_mutable(shard_id="shard-0", segment_id="seg-a", generation=1)
    db.upsert(vector_id="b", embedding=[0.0, 1.0], metadata={}, shard_id="shard-1")
    db.flush_mutable(shard_id="shard-1", segment_id="seg-b", generation=1)
    db.upsert(vector_id="tail-a", embedding=[0.8, 0.2], metadata={}, shard_id="shard-0")
    db.upsert(vector_id="tail-b", embedding=[0.2, 0.8], metadata={}, shard_id="shard-1")

    recovered = ShowcaseLocalDatabase(collection_id="documents", root_dir=tmp_path)
    applied_a = recovered.recover(shard_id="shard-0")
    applied_b = recovered.recover(shard_id="shard-1")

    assert applied_a == 1
    assert applied_b == 1
    assert {entry.record.vector_id for entry in recovered._get_mutable_buffer("shard-0").live_entries()} == {"tail-a"}
    assert {entry.record.vector_id for entry in recovered._get_mutable_buffer("shard-1").live_entries()} == {"tail-b"}
