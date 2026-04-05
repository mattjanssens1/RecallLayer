from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


Precision = Literal["fp32", "fp16", "int8"]


class VectorRecord(BaseModel):
    """Client-visible logical row state."""

    model_config = ConfigDict(extra="forbid")

    collection_id: str
    vector_id: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    shard_id: str = "shard-0"
    active_segment_id: str | None = None
    embedding_version: str
    quantizer_version: str
    latest_write_epoch: int = Field(ge=0)
    is_deleted: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CompressedRecord(BaseModel):
    """Physical payload used for candidate generation."""

    model_config = ConfigDict(extra="forbid")

    segment_id: str
    local_docno: int = Field(ge=0)
    vector_id: str
    code: bytes
    residual_bits: bytes | None = None
    norm: float | None = None
    filter_row_id: int | None = None
    deleted_bit: bool = False


class RerankRecord(BaseModel):
    """Higher-precision payload used for reranking."""

    model_config = ConfigDict(extra="forbid")

    vector_id: str
    rerank_vector: bytes
    precision: Precision
    checksum: str | None = None
    warm_tier_ref: str
