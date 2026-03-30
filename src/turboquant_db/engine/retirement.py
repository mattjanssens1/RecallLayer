from dataclasses import dataclass, replace

from turboquant_db.model.manifest import SegmentManifest, SegmentState


@dataclass(slots=True)
class RetirementDecision:
    next_active_segment_ids: list[str]
    retired_segment_ids: list[str]


def build_retirement_decision(
    *,
    current_active_segment_ids: list[str],
    replacement_segment_id: str,
    retired_segment_ids: list[str],
) -> RetirementDecision:
    remaining = [segment_id for segment_id in current_active_segment_ids if segment_id not in set(retired_segment_ids)]
    next_active = [*remaining, replacement_segment_id]
    return RetirementDecision(next_active_segment_ids=next_active, retired_segment_ids=list(retired_segment_ids))


def apply_retirement(manifests: list[SegmentManifest], *, retired_segment_ids: list[str]) -> list[SegmentManifest]:
    retired = set(retired_segment_ids)
    updated: list[SegmentManifest] = []
    for manifest in manifests:
        if manifest.segment_id in retired:
            updated.append(replace(manifest, state=SegmentState.RETIRED))
        else:
            updated.append(manifest)
    return updated
