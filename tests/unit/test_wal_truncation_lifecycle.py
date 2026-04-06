"""Named contract tests for WAL truncation lifecycle.

These tests define the expected behavior when flush_mutable is called with
truncate_write_log=True.  They must stay green as the storage engine evolves.

Contract: after a flush with truncation, the WAL contains only entries with
write_epoch > replay_from_write_epoch recorded in the shard manifest.  Recovery
replays exactly that tail — no more, no less.
"""
from __future__ import annotations

from pathlib import Path

from recalllayer.engine.showcase_db import ShowcaseLocalDatabase


def test_wal_is_empty_after_flush_with_truncation(tmp_path: Path) -> None:
    """Flushing all mutable data with truncation leaves an empty WAL."""
    db = ShowcaseLocalDatabase(collection_id="documents", root_dir=tmp_path)
    db.upsert(vector_id="a", embedding=[1.0, 0.0], metadata={})
    db.upsert(vector_id="b", embedding=[0.0, 1.0], metadata={})

    db.flush_mutable(segment_id="seg-1", generation=1, truncate_write_log=True)

    remaining = list(db.write_log.replay(after_write_epoch=0))
    assert remaining == []


def test_wal_retains_only_post_flush_entries_after_truncation(tmp_path: Path) -> None:
    """Entries written after the flush are preserved; pre-flush entries are gone."""
    db = ShowcaseLocalDatabase(collection_id="documents", root_dir=tmp_path)
    db.upsert(vector_id="a", embedding=[1.0, 0.0], metadata={})
    db.flush_mutable(segment_id="seg-1", generation=1, truncate_write_log=True)
    db.upsert(vector_id="b", embedding=[0.0, 1.0], metadata={})

    remaining = list(db.write_log.replay(after_write_epoch=0))
    assert len(remaining) == 1
    assert remaining[0].vector_id == "b"


def test_wal_stays_bounded_across_many_flush_cycles(tmp_path: Path) -> None:
    """After N flush+truncate cycles each with M writes, WAL contains at most M entries."""
    db = ShowcaseLocalDatabase(collection_id="documents", root_dir=tmp_path)

    for cycle in range(5):
        for i in range(10):
            db.upsert(vector_id=f"v-{cycle}-{i}", embedding=[float(i), float(cycle)], metadata={})
        db.flush_mutable(
            segment_id=f"seg-{cycle}", generation=cycle + 1, truncate_write_log=True
        )

    # After all flushes with truncation the WAL should be empty (no pending writes).
    remaining = list(db.write_log.replay(after_write_epoch=0))
    assert remaining == []


def test_recovery_after_flush_with_truncation_replays_nothing(tmp_path: Path) -> None:
    """After a flush+truncate with no subsequent writes, recovery has nothing to replay."""
    db = ShowcaseLocalDatabase(collection_id="documents", root_dir=tmp_path)
    db.upsert(vector_id="a", embedding=[1.0, 0.0], metadata={"region": "us"})
    db.upsert(vector_id="b", embedding=[0.0, 1.0], metadata={"region": "ca"})
    db.flush_mutable(segment_id="seg-1", generation=1, truncate_write_log=True)

    recovered = ShowcaseLocalDatabase(collection_id="documents", root_dir=tmp_path)
    applied = recovered.recover()

    assert applied == 0
    assert recovered.mutable_buffer.live_entries() == []
    results = recovered.query_exact_hybrid([1.0, 0.0], top_k=2)
    assert set(results) == {"a", "b"}


def test_recovery_after_flush_with_truncation_replays_newer_tail(tmp_path: Path) -> None:
    """After a flush+truncate, recovery replays only writes that came after the flush."""
    db = ShowcaseLocalDatabase(collection_id="documents", root_dir=tmp_path)
    db.upsert(vector_id="a", embedding=[1.0, 0.0], metadata={})
    db.flush_mutable(segment_id="seg-1", generation=1, truncate_write_log=True)
    db.upsert(vector_id="b", embedding=[0.0, 1.0], metadata={})

    recovered = ShowcaseLocalDatabase(collection_id="documents", root_dir=tmp_path)
    applied = recovered.recover()

    assert applied == 1
    live_ids = {e.record.vector_id for e in recovered.mutable_buffer.live_entries()}
    assert live_ids == {"b"}
    results = recovered.query_exact_hybrid([1.0, 0.0], top_k=2)
    assert set(results) == {"a", "b"}


def test_auto_flush_truncates_wal_when_threshold_triggered(tmp_path: Path) -> None:
    """Auto-flush (flush_threshold) truncates the WAL so it stays bounded."""
    db = ShowcaseLocalDatabase(
        collection_id="documents", root_dir=tmp_path, flush_threshold=3
    )

    # Write enough to trigger two auto-flushes (threshold=3, so flush at 3 and 6 entries).
    for i in range(6):
        db.upsert(vector_id=f"v{i}", embedding=[float(i), 0.0], metadata={})

    # After auto-flushes with truncation, WAL should contain at most the entries
    # from the last partial batch (0 here since both batches were exactly threshold size).
    remaining = list(db.write_log.replay(after_write_epoch=0))
    assert len(remaining) == 0
