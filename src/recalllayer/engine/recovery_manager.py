from __future__ import annotations

from recalllayer.engine.mutable_buffer import MutableBuffer
from recalllayer.engine.write_log import WriteLog, WriteOperation


class RecoveryManager:
    """Rebuilds mutable state by replaying the write log."""

    def __init__(self, *, write_log: WriteLog, mutable_buffer: MutableBuffer) -> None:
        self.write_log = write_log
        self.mutable_buffer = mutable_buffer

    def replay(self, *, embedding_version: str, quantizer_version: str, after_write_epoch: int = 0) -> int:
        applied = 0
        for entry in self.write_log.replay(after_write_epoch=after_write_epoch):
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
