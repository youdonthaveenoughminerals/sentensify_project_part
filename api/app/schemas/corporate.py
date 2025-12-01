from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


def _now_unix_ms() -> int:
    return int(datetime.utcnow().timestamp() * 1000)


def _now_unix_seconds() -> int:
    return int(datetime.utcnow().timestamp())


class BaseCorporateEvent(BaseModel):
    distinct_id: str = Field(default="anonymous")
    device_id: Optional[str] = None
    user_id: Optional[str] = None
    insert_id: str = Field(default_factory=lambda: str(uuid4()))
    time: int = Field(default_factory=_now_unix_seconds)
    mp_api_timestamp_ms: Optional[int] = Field(default_factory=_now_unix_ms)
    browser: Optional[str] = None
    os: Optional[str] = None
    current_url: Optional[str] = None
    referrer: Optional[str] = None
    mp_country_code: Optional[str] = None


class CorporateRunLog(BaseCorporateEvent):
    llm_name: Optional[str] = None
    llm_provider: Optional[str] = None
    maintenance: Optional[str] = None
    target_language: Optional[str] = None
    tone: Optional[str] = None
    input_sentence_length: Optional[int] = None
    field: Optional[str] = None
    platform: Optional[str] = None
    trigger: Optional[str] = None
    response_time_ms: Optional[int] = None


class CorporateSelectLog(BaseCorporateEvent):
    index: Optional[int] = None
    selected_sentence_id: Optional[str] = None
    total_paraphrasing_sentence_count: Optional[int] = None
    maintenance: Optional[str] = None
    field: Optional[str] = None
    target_language: Optional[str] = None


class CorrectionHistory(BaseModel):
    user: Optional[str] = None
    field: Optional[str] = None
    intensity: Optional[str] = None
    user_prompt: Optional[str] = None
    input_sentence: Optional[str] = None
    output_sentences: List[str] = Field(default_factory=list)
    selected_index: Optional[int] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
