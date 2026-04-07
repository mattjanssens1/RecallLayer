from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class SegmentState(StrEnum):
    BUILDING = "building"
    SEALED = "sealed"
    ACTIVE = "active"
    COMPACTING = "compacting"
    RETIRED = "retired"


class ShardState(StrEnum):
    ACTIVE = "active"
    DRAINING = "draining"
    REBALANCING = "rebalancing"
    OFFLINE = "offline"


class SegmentManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    segment_id: str
    collection_id: str
    shard_id: str
    generation: int = Field(ge=0)
    state: SegmentState = SegmentState.BUILDING
    row_count: int = Field(default=0, ge=0)
    live_row_count: int = Field(default=0, ge=0)
    deleted_row_count: int = Field(default=0, ge=0)
    embedding_version: str
    quantizer_version: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    sealed_at: datetime | None = None
    activated_at: datetime | None = None
    min_write_epoch: int = Field(default=0, ge=0)
    max_write_epoch: int = Field(default=0, ge=0)
    content_sha256: str | None = None


class ShardManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    shard_id: str
    collection_id: str
    state: ShardState = ShardState.ACTIVE
    hot_tier_location: str = "memory://local"
    warm_tier_location: str = "file://local"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    active_segment_ids: list[str] = Field(default_factory=list)
    replay_from_write_epoch: int = Field(default=0, ge=0)
