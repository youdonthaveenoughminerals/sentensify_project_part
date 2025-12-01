from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class DocumentBlock(BaseModel):
    block_index: int = Field(..., ge=0)
    text: str = Field(...)


class FullDocumentStore(BaseModel):
    """Schema K – full document representation stored in MongoDB."""

    doc_id: str = Field(..., description="Unique identifier for the document")
    user_id: str = Field(..., description="Owner of the document")
    blocks: List[DocumentBlock] = Field(
        default_factory=list, description="Structured blocks composing the document"
    )
    latest_full_text: str = Field(
        ...,
        description="Latest known full text of the document",
    )
    previous_full_text: Optional[str] = Field(
        default=None,
        description="Previous snapshot for diff comparison",
    )
    diff_ratio: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Levenshtein-based diff ratio between previous and latest text",
    )
    last_synced_at: datetime = Field(
        default_factory=_utcnow,
        description="UTC timestamp when snapshot was last synced",
    )
    schema_version: str = Field(
        default="v2.3",
        description="Schema identifier for FullDocumentStore",
    )

    class Config:
        json_encoders = {datetime: lambda dt: dt.astimezone(timezone.utc).isoformat()}
