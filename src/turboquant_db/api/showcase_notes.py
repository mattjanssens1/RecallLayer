from __future__ import annotations

from typing import Any


def build_collection_notes(*, collection_id: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    notes: dict[str, Any] = {"collection_id": collection_id}
    if extra:
        notes.update(extra)
    return notes
