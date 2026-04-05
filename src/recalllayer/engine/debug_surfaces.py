from __future__ import annotations

from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from recalllayer.engine.recovery_audit import build_recovery_audit
from recalllayer.engine.wal_snapshot import build_write_log_snapshot
from recalllayer.engine.write_log import WriteLog


class DebugEngineSurface:
    def __init__(self, *, root_dir: str | Path, collection_id: str) -> None:
        self.root_dir = Path(root_dir)
        self.collection_id = collection_id
        self.write_log = WriteLog(self.root_dir / collection_id / "write_log.jsonl")

    def recovery_audit(self) -> list[dict[str, Any]]:
        return [_serialize(row) for row in build_recovery_audit(self.write_log)]

    def wal_snapshot(self) -> dict[str, Any]:
        return _serialize(build_write_log_snapshot(self.write_log))


def _serialize(value: Any):
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, list):
        return [_serialize(item) for item in value]
    return value
