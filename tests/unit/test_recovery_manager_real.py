from pathlib import Path

from turboquant_db.engine.mutable_buffer import MutableBuffer
from turboquant_db.engine.recovery_manager import RecoveryManager
from turboquant_db.engine.write_log import WriteLog


def test_recovery_manager_replays_latest_state(tmp_path: Path) -> None:
    write_log = WriteLog(tmp_path / "writes.jsonl")
    write_log.append_upsert(
        collection_id="documents",
        vector_id="doc-1",
        write_epoch=1,
        embedding=[1.0, 0.0],
        metadata={"region": "us"},
    )
    write_log.append_delete(
        collection_id="documents",
        vector_id="doc-1",
        write_epoch=2,
    )

    buffer = MutableBuffer(collection_id="documents")
    manager = RecoveryManager(write_log=write_log, mutable_buffer=buffer)
    applied = manager.replay(embedding_version="embed-v1", quantizer_version="tq-v0")

    assert applied == 2
    entry = buffer.get("doc-1")
    assert entry is not None
    assert entry.record.is_deleted is True
