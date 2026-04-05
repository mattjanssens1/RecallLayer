from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from turboquant_db.api.schemas import QueryHit


class QueryTrace(BaseModel):
    mode: str
    top_k: int
    filters_applied: bool
    mutable_live_count: int
    sealed_segment_count: int
    result_count: int
    rerank_candidate_k: int | None = None
    notes: dict[str, Any] = Field(default_factory=dict)


class TraceableQueryResponse(BaseModel):
    results: list[QueryHit]
    mode: str
    trace: QueryTrace
