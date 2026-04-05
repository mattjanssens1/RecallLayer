from __future__ import annotations

import json
from pathlib import Path

from recalllayer.model.manifest import ShardManifest


class ManifestStore:
    """Very small local manifest store for shard state.

    This will eventually need atomic swaps and versioning. For now it provides
    a single durable file per shard so the engine has an explicit source of truth.
    """

    def __init__(self, root_dir: str | Path) -> None:
        self.root_dir = Path(root_dir)
        self.root_dir.mkdir(parents=True, exist_ok=True)

    def _path_for(self, collection_id: str, shard_id: str) -> Path:
        collection_dir = self.root_dir / collection_id
        collection_dir.mkdir(parents=True, exist_ok=True)
        return collection_dir / f"{shard_id}.manifest.json"

    def save(self, manifest: ShardManifest) -> Path:
        path = self._path_for(manifest.collection_id, manifest.shard_id)
        payload = manifest.model_dump(mode="json")
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        return path

    def load(self, *, collection_id: str, shard_id: str) -> ShardManifest | None:
        path = self._path_for(collection_id, shard_id)
        if not path.exists():
            return None
        return ShardManifest.model_validate_json(path.read_text(encoding="utf-8"))
