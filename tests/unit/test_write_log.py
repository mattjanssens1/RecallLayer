from pathlib import Path

from recalllayer.engine.write_log import WriteLog, WriteOperation


def test_write_log_replays_upsert_and_delete(tmp_path: Path) -> None:
    log = WriteLog(tmp_path / "writes.jsonl")
    log.append_upsert(
        collection_id="documents",
        vector_id="doc-1",
        write_epoch=1,
        embedding=[1.0, 0.0],
        metadata={"region": "us"},
    )
    log.append_delete(
        collection_id="documents",
        vector_id="doc-1",
        write_epoch=2,
    )

    entries = list(log.replay())

    assert len(entries) == 2
    assert entries[0].operation == WriteOperation.UPSERT
    assert entries[1].operation == WriteOperation.DELETE
    assert entries[0].metadata["region"] == "us"
    assert entries[1].write_epoch == 2
