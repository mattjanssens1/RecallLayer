from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from threading import RLock
from typing import Any

from turboquant_db.model.records import VectorRecord


@dataclass(slots=True)
class MutableBufferEntry:
    """In-memory latest-visible mutable state for a vector id."""

    record: VectorRecord
    embedding: list[float] | None
    metadata: dict[str, Any]
    updated_at: datetime


class MutableBuffer:
    """Realtime in-memory buffer for upserts and tombstones."""

    def __init__(self, collection_id: str) -> None:
        self.collection_id = collection_id
        self._entries: dict[str, MutableBufferEntry] = {}
        self._lock = RLock()

    def upsert(
        self,
        *,
        vector_id: str,
        embedding: list[float],
        metadata: dict[str, Any],
        embedding_version: str,
        quantizer_version: str,
        write_epoch: int,
        shard_id: str = "shard-0",
    ) -> VectorRecord:
        with self._lock:
            current = self._entries.get(vector_id)
            if current is not None and current.record.latest_write_epoch > write_epoch:
                return current.record

            now = datetime.now(timezone.utc)
            created_at = current.record.created_at if current is not None else now
            record = VectorRecord(
                collection_id=self.collection_id,
                vector_id=vector_id,
                metadata=metadata,
                shard_id=shard_id,
                embedding_version=embedding_version,
                quantizer_version=quantizer_version,
                latest_write_epoch=write_epoch,
                is_deleted=False,
                created_at=created_at,
                updated_at=now,
            )
            self._entries[vector_id] = MutableBufferEntry(
                record=record,
                embedding=list(embedding),
                metadata=dict(metadata),
                updated_at=now,
            )
            return record

    def delete(
        self,
        *,
        vector_id: str,
        embedding_version: str,
        quantizer_version: str,
        write_epoch: int,
        shard_id: str = "shard-0",
    ) -> VectorRecord:
        with self._lock:
            current = self._entries.get(vector_id)
            if current is not None and current.record.latest_write_epoch > write_epoch:
                return current.record

            now = datetime.now(timezone.utc)
            created_at = current.record.created_at if current is not None else now
            metadata = current.metadata if current is not None else {}
            record = VectorRecord(
                collection_id=self.collection_id,
                vector_id=vector_id,
                metadata=metadata,
                shard_id=shard_id,
                embedding_version=embedding_version,
                quantizer_version=quantizer_version,
                latest_write_epoch=write_epoch,
                is_deleted=True,
                created_at=created_at,
                updated_at=now,
            )
            self._entries[vector_id] = MutableBufferEntry(
                record=record,
                embedding=None,
                metadata=dict(metadata),
                updated_at=now,
            )
            return record

    def get(self, vector_id: str) -> MutableBufferEntry | None:
        with self._lock:
            return self._entries.get(vector_id)

    def live_entries(self) -> list[MutableBufferEntry]:
        with self._lock:
            return [entry for entry in self._entries.values() if not entry.record.is_deleted]

    def watermark(self) -> int:
        with self._lock:
            if not self._entries:
                return 0
            return max(entry.record.latest_write_epoch for entry in self._entries.values())
