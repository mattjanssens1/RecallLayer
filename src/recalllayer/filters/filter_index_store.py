from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from recalllayer.filters.indexes import FilterIndexes, MetadataRow

_FORMAT_VERSION = "v1"


class FilterIndexStore:
    """Persists and loads per-segment metadata filter indexes alongside segment files.

    Each sealed segment gets a companion ``{segment_id}.filter_index.json`` file
    written at flush time.  At query time the file is loaded back as a
    ``FilterIndexes`` instance, enabling pre-filter candidate pruning without
    scanning the full segment JSONL.

    File format::

        {
          "format_version": "v1",
          "segment_id": "seg-1",
          "rows": [
            {"vector_id": "vec-0", "metadata": {"region": "us", "tier": 1}},
            ...
          ]
        }
    """

    def segment_filter_path(self, segment_path: Path) -> Path:
        """Return the filter-index path for a given segment path."""
        return segment_path.with_suffix("").with_suffix(".filter_index.json")

    def save(self, segment_path: Path, segment_id: str, rows: list[MetadataRow]) -> Path:
        """Write a filter index for *segment_id* alongside *segment_path*.

        Args:
            segment_path: Path to the ``.segment.jsonl`` file.
            segment_id: Segment identifier stored in the index header.
            rows: Metadata rows for every live (non-deleted) vector in the segment.

        Returns:
            Path to the written filter index file.
        """
        filter_path = self.segment_filter_path(segment_path)
        payload: dict[str, Any] = {
            "format_version": _FORMAT_VERSION,
            "segment_id": segment_id,
            "rows": [{"vector_id": row.vector_id, "metadata": row.metadata} for row in rows],
        }
        filter_path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
        return filter_path

    def load(self, segment_path: Path) -> FilterIndexes | None:
        """Load a ``FilterIndexes`` from the companion file for *segment_path*.

        Returns ``None`` if the companion file does not exist (e.g. legacy
        segments written before this feature was added).
        """
        filter_path = self.segment_filter_path(segment_path)
        if not filter_path.exists():
            return None
        try:
            payload = json.loads(filter_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        if payload.get("format_version") not in {_FORMAT_VERSION}:
            return None
        rows = [
            MetadataRow(vector_id=r["vector_id"], metadata=r.get("metadata", {}))
            for r in payload.get("rows", [])
        ]
        return FilterIndexes(rows)
