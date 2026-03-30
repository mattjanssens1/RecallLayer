from __future__ import annotations

import json
from pathlib import Path

from turboquant_db.model.manifest import SegmentManifest


class SegmentManifestStore:
    """Local helper for saving and loading per-segment manifests."""

    def __init__(self, root_dir: str | Path) -> None:
        self.root_dir = Path(root_dir)
        self.root_dir.mkdir(parents=True, exist_ok=True)

    def _path_for(self, *, collection_id: str, shard_id: str, segment_id: str) -> Path:
        shard_dir = self.root_dir / collection_id / shard_id
        shard_dir.mkdir(parents=True, exist_ok=True)
        return shard_dir / f"{segment_id}.manifest.json"

    def save(self, manifest: SegmentManifest) -> Path:
        path = self._path_for(
            collection_id=manifest.collection_id,
            shard_id=manifest.shard_id,
            segment_id=manifest.segment_id,
        )
        payload = manifest.model_dump(mode="json")
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        return path

    def load(self, *, collection_id: str, shard_id: str, segment_id: str) -> SegmentManifest | None:
        path = self._path_for(collection_id=collection_id, shard_id=shard_id, segment_id=segment_id)
        if not path.exists():
            return None
        return SegmentManifest.model_validate_json(path.read_text(encoding="utf-8"))

    def list_manifests(self, *, collection_id: str, shard_id: str) -> list[SegmentManifest]:
        shard_dir = self.root_dir / collection_id / shard_id
        if not shard_dir.exists():
            return []
        manifests: list[SegmentManifest] = []
        for path in sorted(shard_dir.glob("*.manifest.json")):
            manifests.append(SegmentManifest.model_validate_json(path.read_text(encoding="utf-8")))
        return manifests
