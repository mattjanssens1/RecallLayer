from turboquant_db.engine.mutable_buffer import MutableBuffer


def test_latest_write_epoch_wins_for_upsert() -> None:
    buffer = MutableBuffer(collection_id="documents")
    buffer.upsert(
        vector_id="doc-1",
        embedding=[1.0, 0.0],
        metadata={"region": "us"},
        embedding_version="embed-v1",
        quantizer_version="tq-v0",
        write_epoch=2,
    )
    buffer.upsert(
        vector_id="doc-1",
        embedding=[0.0, 1.0],
        metadata={"region": "ca"},
        embedding_version="embed-v1",
        quantizer_version="tq-v0",
        write_epoch=1,
    )

    entry = buffer.get("doc-1")
    assert entry is not None
    assert entry.record.latest_write_epoch == 2
    assert entry.metadata["region"] == "us"


def test_delete_hides_live_entry() -> None:
    buffer = MutableBuffer(collection_id="documents")
    buffer.upsert(
        vector_id="doc-2",
        embedding=[1.0, 0.0],
        metadata={"region": "us"},
        embedding_version="embed-v1",
        quantizer_version="tq-v0",
        write_epoch=1,
    )
    buffer.delete(
        vector_id="doc-2",
        embedding_version="embed-v1",
        quantizer_version="tq-v0",
        write_epoch=2,
    )

    entry = buffer.get("doc-2")
    assert entry is not None
    assert entry.record.is_deleted is True
    assert buffer.live_entries() == []
