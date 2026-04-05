from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SidecarDocumentUpsertRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    body: str
    region: str
    status: str = "published"


class SidecarQueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query_text: str
    top_k: int = Field(default=3, ge=1)
    region: str | None = None


class SidecarRepairRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_ids: list[str] | None = None


class SidecarFlushRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    segment_id: str = "seg-1"
    generation: int = Field(default=1, ge=1)


class SidecarCompactionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    output_segment_id: str = "seg-compacted"
    generation: int = Field(default=1, ge=1)
    min_segment_count: int = Field(default=2, ge=2)
    max_total_rows: int = Field(default=1000, ge=1)


class SidecarCandidateHit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vector_id: str
    score: float
    metadata: dict[str, Any] = Field(default_factory=dict)


class SidecarHydratedDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: str
    vector_id: str
    title: str
    body: str
    region: str
    status: str


class SidecarSearchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str
    candidate_ids: list[str]
    candidates: list[SidecarCandidateHit]
    hydrated_results: list[SidecarHydratedDocument]
