from dataclasses import dataclass
from pathlib import Path

from turboquant_db.model.manifest import SegmentManifest, SegmentState


@dataclass(slots=True)
class SegmentGarbageCandidate:
    segment_id: str
    segment_path: Path
    manifest_path: Path


@dataclass(slots=True)
class SegmentGarbageCollectionResult:
    removed_segment_ids: list[str]
    removed_paths: list[Path]


def plan_segment_garbage_collection(
    *,
    manifests: list[SegmentManifest],
    segments_root: str | Path,
) -> list[SegmentGarbageCandidate]:
    root = Path(segments_root)
    candidates: list[SegmentGarbageCandidate] = []
    for manifest in manifests:
        if manifest.state != SegmentState.RETIRED:
            continue
        shard_dir = root / manifest.collection_id / manifest.shard_id
        candidates.append(
            SegmentGarbageCandidate(
                segment_id=manifest.segment_id,
                segment_path=shard_dir / f"{manifest.segment_id}.segment.jsonl",
                manifest_path=shard_dir / f"{manifest.segment_id}.manifest.json",
            )
        )
    return candidates


def execute_segment_garbage_collection(candidates: list[SegmentGarbageCandidate]) -> SegmentGarbageCollectionResult:
    removed_segment_ids: list[str] = []
    removed_paths: list[Path] = []
    for candidate in candidates:
        for path in [candidate.segment_path, candidate.manifest_path]:
            if path.exists():
                path.unlink()
                removed_paths.append(path)
        removed_segment_ids.append(candidate.segment_id)
    return SegmentGarbageCollectionResult(removed_segment_ids=removed_segment_ids, removed_paths=removed_paths)
