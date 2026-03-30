from dataclasses import dataclass
from pathlib import Path

from turboquant_db.model.manifest import SegmentManifest, SegmentState


@dataclass(slots=True)
class SegmentGarbageCandidate:
    segment_id: str
    segment_path: Path
    manifest_path: Path


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
