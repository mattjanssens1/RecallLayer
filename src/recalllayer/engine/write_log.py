from __future__ import annotations

import json
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from threading import Lock
from typing import Any, Iterable

from pydantic import BaseModel, ConfigDict, Field


class WriteOperation(StrEnum):
    UPSERT = "upsert"
    DELETE = "delete"


class WriteLogEntry(BaseModel):
    """Single durable write-log entry."""

    model_config = ConfigDict(extra="forbid")

    operation: WriteOperation
    collection_id: str
    vector_id: str
    write_epoch: int = Field(ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)
    embedding: list[float] | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class WriteLog:
    """Very small JSONL write log for prototype durability and replay."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()

    def append(self, entry: WriteLogEntry) -> None:
        payload = entry.model_dump(mode="json")
        encoded = json.dumps(payload, separators=(",", ":"))
        with self._lock:
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(encoded)
                handle.write("\n")

    def append_upsert(
        self,
        *,
        collection_id: str,
        vector_id: str,
        write_epoch: int,
        embedding: list[float],
        metadata: dict[str, Any] | None = None,
    ) -> WriteLogEntry:
        entry = WriteLogEntry(
            operation=WriteOperation.UPSERT,
            collection_id=collection_id,
            vector_id=vector_id,
            write_epoch=write_epoch,
            embedding=embedding,
            metadata=metadata or {},
        )
        self.append(entry)
        return entry

    def append_delete(
        self,
        *,
        collection_id: str,
        vector_id: str,
        write_epoch: int,
    ) -> WriteLogEntry:
        entry = WriteLogEntry(
            operation=WriteOperation.DELETE,
            collection_id=collection_id,
            vector_id=vector_id,
            write_epoch=write_epoch,
        )
        self.append(entry)
        return entry

    def truncate_before(self, write_epoch: int) -> int:
        """Remove all entries with write_epoch <= *write_epoch*.

        Rewrites the log file atomically.  Returns the count of removed entries.
        """
        if not self.path.exists():
            return 0

        kept: list[str] = []
        removed = 0
        with self.path.open("r", encoding="utf-8") as handle:
            for line in handle:
                stripped = line.strip()
                if not stripped:
                    continue
                entry = WriteLogEntry.model_validate_json(stripped)
                if entry.write_epoch <= write_epoch:
                    removed += 1
                else:
                    kept.append(stripped)

        tmp = self.path.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as handle:
            for line in kept:
                handle.write(line)
                handle.write("\n")
        tmp.replace(self.path)
        return removed

    def replay(self, *, after_write_epoch: int = 0) -> Iterable[WriteLogEntry]:
        if not self.path.exists():
            return []

        entries: list[WriteLogEntry] = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                entry = WriteLogEntry.model_validate_json(line)
                if entry.write_epoch <= after_write_epoch:
                    continue
                entries.append(entry)
        return entries
