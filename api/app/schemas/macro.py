from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class DocumentContextCache(BaseModel):
    """Schema F – macro context cache stored in Redis."""

    doc_id: str = Field(..., description="Unique identifier for the document")
    macro_topic: str = Field(
        ..., description="High level topic extracted for macro reasoning"
    )
    macro_category_hint: str = Field(
        ..., description="Hint used to nudge downstream macro classifiers"
    )
    macro_llm_version: str = Field(
        ..., description="LLM version that produced the macro context"
    )
    cache_hit_count: int = Field(
        default=0,
        ge=0,
        description="How many times the cache entry has served requests",
    )
    last_updated: datetime = Field(
        default_factory=_utcnow,
        description="UTC timestamp for the last successful update",
    )
    valid_until: datetime = Field(
        ..., description="UTC timestamp indicating cache validity period"
    )
    invalidated_by_diff: bool = Field(
        default=False,
        description="True when the cache was invalidated by a diff event",
    )
    diff_ratio: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Normalized diff ratio (0~1) against the previous snapshot",
    )
    schema_version: str = Field(
        default="v2.3",
        description="Schema identifier for macro context cache entries",
    )

    class Config:
        json_encoders = {datetime: lambda dt: dt.astimezone(timezone.utc).isoformat()}
