from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from recalllayer.engine.segment_gc import (
    SegmentGarbageCollectionResult,
    execute_segment_garbage_collection,
    plan_segment_garbage_collection,
)
from recalllayer.engine.segment_manifest_store import SegmentManifestStore


@dataclass(slots=True)
class SegmentGarbageCollectionExecution:
    shard_id: str
    collection_id: str
    candidate_segment_ids: list[str]
    result: SegmentGarbageCollectionResult


class SegmentGarbageCollectionExecutor:
    def __init__(self, *, segment_manifest_store: SegmentManifestStore, segments_root: str | Path, manifests_root: str | Path | None = None) -> None:
        self.segment_manifest_store = segment_manifest_store
        self.segments_root = Path(segments_root)
        self.manifests_root = Path(manifests_root) if manifests_root is not None else None

    def collect_shard(self, *, collection_id: str, shard_id: str = 'shard-0') -> SegmentGarbageCollectionExecution:
        manifests = self.segment_manifest_store.list_manifests(collection_id=collection_id, shard_id=shard_id)
        candidates = plan_segment_garbage_collection(
            manifests=manifests,
            segments_root=self.segments_root,
            manifests_root=self.manifests_root,
        )
        result = execute_segment_garbage_collection(candidates)
        return SegmentGarbageCollectionExecution(
            shard_id=shard_id,
            collection_id=collection_id,
            candidate_segment_ids=[candidate.segment_id for candidate in candidates],
            result=result,
        )
