from __future__ import annotations

from turboquant_db.engine.mutable_buffer import MutableBuffer
from turboquant_db.engine.write_log import WriteLog, WriteOperation


class RecoveryManager:
    """Rebuilds mutable state by replaying the write log."""

    def __init__(self, *, write_log: WriteLog, mutable_buffer: MutableBuffer) -> None:
        self.write_log = write_log
        self.mutable_buffer = mutable_buffer

    def replay(self, *, embedding_version: str, quantizer_version: str) -> int:
        applied = 0
        for entry in self.write_log.replay():
            if entry.operation == WriteOperation.UPSERT:
                if entry.embedding is None:
                    continue
                self.mutable_buffer.upsert(
                    vector_id=entry.vector_id,
                    embedding=entry.embedding,
                    metadata=entry.metadata,
                    embedding_version=embedding_version,
                    quantizer_version=quantizer_version,
                    write_epoch=entry.write_epoch,
                )
                applied += 1
                continue

            if entry.operation == WriteOperation.DELETE:
                self.mutable_buffer.delete(
                    vector_id=entry.vector_id,
                    embedding_version=embedding_version,
                    quantizer_version=quantizer_version,
                    write_epoch=entry.write_epoch,
                )
                applied += 1
        return applied
