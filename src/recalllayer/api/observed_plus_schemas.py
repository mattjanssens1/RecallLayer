from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from recalllayer.api.schemas import QueryHit


class ObservedPlusQueryTrace(BaseModel):
    mode: str
    top_k: int
    filters_applied: bool
    mutable_live_count: int
    sealed_segment_count: int
    sealed_segment_ids: list[str] = Field(default_factory=list)
    result_count: int
    mutable_hit_count: int
    sealed_hit_count: int
    rerank_candidate_k: int | None = None
    latency_ms: float
    candidate_count_estimate: int
    pre_filter_candidate_estimate: int | None = None
    post_filter_candidate_estimate: int | None = None
    notes: dict[str, Any] = Field(default_factory=dict)


class ObservedPlusQueryResponse(BaseModel):
    results: list[QueryHit]
    mode: str
    trace: ObservedPlusQueryTrace
