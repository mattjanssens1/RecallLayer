from pathlib import Path

from recalllayer.engine.wal_snapshot import build_write_log_snapshot
from recalllayer.engine.write_log import WriteLog


def test_build_write_log_snapshot_tracks_live_and_deleted_vectors(tmp_path: Path) -> None:
    log = WriteLog(tmp_path / "write_log.jsonl")
    log.append_upsert(collection_id="documents", vector_id="a", write_epoch=1, embedding=[1.0])
    log.append_upsert(collection_id="events", vector_id="evt-1", write_epoch=2, embedding=[0.2])
    log.append_delete(collection_id="documents", vector_id="a", write_epoch=3)

    snapshot = build_write_log_snapshot(log)

    assert snapshot.total_entries == 3
    assert snapshot.collection_count == 2
    assert snapshot.live_vector_count == 1
    assert snapshot.deleted_vector_count == 1
    assert snapshot.latest_write_epoch == 3
