from dataclasses import dataclass

from turboquant_db.engine.write_log import WriteLog, WriteOperation


@dataclass(slots=True)
class WriteLogSnapshot:
    total_entries: int
    collection_count: int
    live_vector_count: int
    deleted_vector_count: int
    latest_write_epoch: int


def build_write_log_snapshot(write_log: WriteLog) -> WriteLogSnapshot:
    latest_by_vector: dict[tuple[str, str], WriteOperation] = {}
    latest_epoch = 0
    collections: set[str] = set()
    total_entries = 0

    for entry in write_log.replay():
        total_entries += 1
        collections.add(entry.collection_id)
        latest_epoch = max(latest_epoch, entry.write_epoch)
        latest_by_vector[(entry.collection_id, entry.vector_id)] = entry.operation

    deleted_vector_count = sum(1 for operation in latest_by_vector.values() if operation == WriteOperation.DELETE)
    live_vector_count = sum(1 for operation in latest_by_vector.values() if operation == WriteOperation.UPSERT)
    return WriteLogSnapshot(
        total_entries=total_entries,
        collection_count=len(collections),
        live_vector_count=live_vector_count,
        deleted_vector_count=deleted_vector_count,
        latest_write_epoch=latest_epoch,
    )
