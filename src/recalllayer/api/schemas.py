from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class QueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    embedding: list[float] = Field(min_length=1)
    top_k: int = Field(gt=0, le=1000)
    approximate: bool = True
    rerank: bool = False
    filters: dict[str, Any] = Field(default_factory=dict)


class QueryHit(BaseModel):
    vector_id: str
    score: float
    metadata: dict[str, Any] = Field(default_factory=dict)


class QueryResponse(BaseModel):
    results: list[QueryHit]
    mode: str


class UpsertRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    embedding: list[float] = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)
