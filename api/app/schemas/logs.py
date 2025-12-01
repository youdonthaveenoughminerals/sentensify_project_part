from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.schemas.corporate import BaseCorporateEvent


class LogA(BaseModel):
    insert_id: Optional[str] = None
    recommend_session_id: Optional[str] = None
    doc_id: Optional[str] = None
    user_id: Optional[str] = None
    reco_options: List[Dict[str, Any]] = Field(default_factory=list)
    P_vec: Dict[str, float] = Field(default_factory=dict)
    P_doc: Dict[str, float] = Field(default_factory=dict)
    applied_weight_doc: float = 0.0
    doc_maturity_score: float = 0.0
    created_at: datetime = Field(default_factory=datetime.utcnow)


class LogB(BaseCorporateEvent):
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
    source_recommend_event_id: Optional[str] = None
    recommend_session_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class LogC(BaseCorporateEvent):
    maintenance: Optional[str] = None
    field: Optional[str] = None
    target_language: Optional[str] = None
    index: Optional[int] = None
    selected_sentence_id: Optional[str] = None
    total_paraphrasing_sentence_count: Optional[int] = None
    source_recommend_event_id: Optional[str] = None
    recommend_session_id: Optional[str] = None
    was_accepted: Optional[bool] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class LogI(BaseModel):
    latency_ms: Optional[int] = None
    model_version: Optional[str] = None
    is_shadow_mode: Optional[bool] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
