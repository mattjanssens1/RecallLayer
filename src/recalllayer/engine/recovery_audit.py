from collections import defaultdict
from dataclasses import dataclass

from recalllayer.engine.write_log import WriteLog, WriteOperation


@dataclass(slots=True)
class RecoveryAuditRow:
    collection_id: str
    total_entries: int
    upsert_count: int
    delete_count: int
    latest_write_epoch: int
    distinct_vector_count: int


def build_recovery_audit(write_log: WriteLog) -> list[RecoveryAuditRow]:
    rows: dict[str, dict[str, object]] = defaultdict(
        lambda: {
            "total_entries": 0,
            "upsert_count": 0,
            "delete_count": 0,
            "latest_write_epoch": 0,
            "vector_ids": set(),
        }
    )

    for entry in write_log.replay():
        row = rows[entry.collection_id]
        row["total_entries"] = int(row["total_entries"]) + 1
        row["latest_write_epoch"] = max(int(row["latest_write_epoch"]), entry.write_epoch)
        row["vector_ids"].add(entry.vector_id)
        if entry.operation == WriteOperation.UPSERT:
            row["upsert_count"] = int(row["upsert_count"]) + 1
        elif entry.operation == WriteOperation.DELETE:
            row["delete_count"] = int(row["delete_count"]) + 1

    audit_rows: list[RecoveryAuditRow] = []
    for collection_id in sorted(rows):
        row = rows[collection_id]
        audit_rows.append(
            RecoveryAuditRow(
                collection_id=collection_id,
                total_entries=int(row["total_entries"]),
                upsert_count=int(row["upsert_count"]),
                delete_count=int(row["delete_count"]),
                latest_write_epoch=int(row["latest_write_epoch"]),
                distinct_vector_count=len(row["vector_ids"]),
            )
        )
    return audit_rows
