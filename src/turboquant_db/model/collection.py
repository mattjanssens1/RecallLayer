from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CollectionState(StrEnum):
    ACTIVE = "active"
    MIGRATING = "migrating"
    READ_ONLY = "read_only"
    ARCHIVED = "archived"


class DistanceMetric(StrEnum):
    COSINE = "cosine"
    DOT_PRODUCT = "dot_product"
    L2 = "l2"


FilterType = Literal["keyword", "int", "float", "bool", "timestamp"]
RerankPrecision = Literal["fp32", "fp16", "int8"]


class CollectionConfig(BaseModel):
    """Stable collection-level configuration for a vector corpus."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    collection_id: str = Field(min_length=1)
    metric: DistanceMetric
    embedding_dim: int = Field(gt=0)
    embedding_version: str = Field(min_length=1)
    quantizer_version: str = Field(min_length=1)
    rerank_precision: RerankPrecision
    filter_schema: dict[str, FilterType] = Field(default_factory=dict)
    write_epoch: int = Field(default=0, ge=0)
    state: CollectionState = CollectionState.ACTIVE
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("collection_id")
    @classmethod
    def validate_collection_id(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("collection_id must not be empty")
        return value
