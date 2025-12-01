from __future__ import annotations

from datetime import datetime
from typing import List, Dict

from pydantic import BaseModel, Field


class UserProfile(BaseModel):
    user_id: str
    
    # 1. Overview
    total_recommend_count: int = 0
    total_accept_count: int = 0
    overall_accept_rate: float = 0.0
    paraphrase_execution_count: int = 0

    # 2. Detailed Accept Rates
    accept_rate_by_feature: Dict[str, float] = Field(default_factory=dict)
    # e.g. {"category": 0.8, "intensity": 0.5}

    # 3. Preference Distribution (Map instead of Vector)
    preferred_category_map: Dict[str, float] = Field(default_factory=dict)
    preferred_intensity_map: Dict[str, float] = Field(default_factory=dict)

    # 4. User Embedding (Phase 3)
    user_embedding_v1: List[float] = Field(default_factory=list)

    updated_at: datetime = Field(default_factory=datetime.utcnow)
    schema_version: str = "v2.4"
