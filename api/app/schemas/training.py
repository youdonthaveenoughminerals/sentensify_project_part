from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional, Any

from pydantic import BaseModel, Field


class MatchMetrics(BaseModel):
    is_category_match: bool = False
    is_intensity_match: bool = False
    is_prompt_match: bool = False
    match_score: int = 0
    winner_engine: str = "unknown"


class TrainingExample(BaseModel):
    # --- Identity ---
    example_id: str
    recommend_session_id: str
    user_id: str
    doc_id: Optional[str] = None

    # --- Features (Input) ---
    context_embedding: List[float] = Field(default_factory=list)
    input_context: Optional[str] = None  # Original Sentence (Crucial for Training)
    macro_category_hint: Optional[str] = None
    reco_category_input: Optional[str] = None
    
    # --- Model Scores ---
    reco_scores_vec: Dict[str, float] = Field(default_factory=dict)  # P_vec
    reco_scores_doc: Dict[str, float] = Field(default_factory=dict)  # P_doc
    reco_scores_rule: Dict[str, float] = Field(default_factory=dict) # P_rule (New)
    reco_options: List[Dict[str, Any]] = Field(default_factory=list) # Full options from A

    # --- Actions (From B - Execution) ---
    executed_target_language: Optional[str] = None
    executed_target_intensity: Optional[str] = None
    executed_target_category: Optional[str] = None
    llm_provider: Optional[str] = None
    response_time_ms: Optional[int] = None

    # --- Labels (Targets - From C/D) ---
    was_accepted: bool = False
    selected_option_index: Optional[int] = None
    
    groundtruth_field: Optional[str] = None
    groundtruth_intensity: Optional[str] = None
    groundtruth_user_prompt: Optional[str] = None
    groundtruth_text: Optional[str] = None # The final text

    # --- Metrics (v2.5 New) ---
    match_metrics: MatchMetrics = Field(default_factory=MatchMetrics)

    # --- Metadata ---
    consistency_flag: str = "high"
    schema_version: str = "v2.5"
    created_at: datetime = Field(default_factory=datetime.utcnow)