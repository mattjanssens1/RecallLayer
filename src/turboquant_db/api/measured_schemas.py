from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from turboquant_db.api.schemas import QueryHit


class MeasuredTimingBreakdown(BaseModel):
    mutable_search_latency_ms: float
    sealed_search_latency_ms: float
    merge_latency_ms: float
    rerank_latency_ms: float
    materialization_latency_ms: float = 0.0


class MeasuredQueryTrace(BaseModel):
    mode: str
    top_k: int
    filters_applied: bool
    mutable_live_count: int
    sealed_segment_count: int
    sealed_segment_ids: list[str] = Field(default_factory=list)
    result_count: int
    mutable_hit_count: int
    sealed_hit_count: int
    pre_filter_candidate_count: int
    post_filter_candidate_count: int
    rerank_candidate_k: int | None = None
    search_latency_ms: float
    rerank_latency_ms: float
    total_latency_ms: float
    timing_breakdown: MeasuredTimingBreakdown
    notes: dict[str, Any] = Field(default_factory=dict)
    exported_trace: dict[str, Any] = Field(default_factory=dict)


class MeasuredQueryResponse(BaseModel):
    results: list[QueryHit]
    mode: str
    trace: MeasuredQueryTrace
