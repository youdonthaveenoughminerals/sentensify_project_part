from __future__ import annotations

import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pymongo import MongoClient

from app.schemas.training import TrainingExample, MatchMetrics
from app.config import MONGO_URI, MONGO_DB_NAME

class EtlService:
    def __init__(self, mongo_client: Optional[MongoClient] = None):
        self.client = mongo_client or MongoClient(MONGO_URI)
        self.db = self.client[MONGO_DB_NAME]
        
        # Input Collections
        self.col_a = self.db["editor_recommend_options"]
        self.col_b = self.db["editor_run_paraphrasing"]
        self.col_c = self.db["editor_selected_paraphrasing"]
        self.col_d = self.db["correction_history"]
        self.col_e = self.db["context_block"]
        
        # Output Collection
        self.col_h = self.db["training_examples"]

    def process_session(self, session_id: str) -> bool:
        """
        Processes a single session to generate a Training Example (H).
        Can be called by background worker immediately after C log is saved.
        """
        if not session_id:
            return False

        try:
            # 1. Fetch Logs
            log_c = self.col_c.find_one({"recommend_session_id": session_id})
            if not log_c:
                print(f"[ETL] Log C not found for session {session_id}")
                return False

            log_a = self.col_a.find_one({"recommend_session_id": session_id})
            log_b = self.col_b.find_one({"recommend_session_id": session_id})
            log_d = self.col_d.find_one({"recommend_session_id": session_id})
            
            # Link A -> E via context_hash
            log_e = None
            if log_a and "context_hash" in log_a:
                log_e = self.col_e.find_one({"context_hash": log_a["context_hash"]})

            # 2. Transform
            example = self._transform_to_example(log_c, log_a, log_b, log_d, log_e)
            
            if not example:
                print(f"[ETL] Transformation failed for session {session_id} (Missing A log?)")
                return False

            # 3. Load (Upsert)
            self.col_h.update_one(
                {"recommend_session_id": session_id},
                {"$set": example.model_dump()},
                upsert=True
            )

            # 4. Mark as Processed (Flagging)
            self.col_c.update_one(
                {"recommend_session_id": session_id},
                {"$set": {"processed_for_training": True}}
            )
            
            print(f"[ETL] Successfully created Training Example for session {session_id}")
            return True

        except Exception as e:
            print(f"[ETL] Error processing session {session_id}: {e}")
            return False

    def run_etl_pipeline(self, limit: int = 100) -> int:
        """
        Batch processing: Find unprocessed C logs and process them.
        """
        # Process unprocessed logs first
        cursor = self.col_c.find({"processed_for_training": {"$ne": True}}).sort("created_at", 1).limit(limit)
        count = 0
        for log_c in cursor:
            sid = log_c.get("recommend_session_id")
            if sid:
                if self.process_session(sid):
                    count += 1
        return count

    def _transform_to_example(
        self, 
        c: Dict, 
        a: Optional[Dict], 
        b: Optional[Dict], 
        d: Optional[Dict], 
        e: Optional[Dict]
    ) -> Optional[TrainingExample]:
        
        if not a:
            # A log is mandatory for 'reco_options' and inputs
            return None

        # --- Extract Features ---
        reco_options = a.get("reco_options", [])
        top_reco = reco_options[0] if reco_options else {}
        
        # Metrics Calculation
        final_category = d.get("field") if d else (b.get("target_category") if b else None)
        final_intensity = d.get("intensity") if d else (b.get("target_intensity") if b else None)
        
        is_cat_match = (top_reco.get("category") == final_category) if final_category else False
        is_int_match = (top_reco.get("intensity") == final_intensity) if final_intensity else False
        
        match_metrics = MatchMetrics(
            is_category_match=is_cat_match,
            is_intensity_match=is_int_match,
            match_score=int(is_cat_match) + int(is_int_match),
            winner_engine="hybrid" # Placeholder logic
        )

        # Ground Truth Text
        gt_text = None
        if d:
            outputs = d.get("output_sentences", [])
            idx = d.get("selected_index", 0)
            if idx is not None and isinstance(outputs, list) and 0 <= idx < len(outputs):
                gt_text = outputs[idx]
        elif c:
            # Fallback to C if D missing (legacy)
            gt_text = c.get("selected_text") or c.get("selected_candidate_text")

        # Embedding: Prioritize D (Dual-Write) -> E (Context Block)
        embedding = []
        if d and d.get("context_embedding"):
            embedding = d.get("context_embedding")
        elif e and e.get("embedding"):
            embedding = e.get("embedding")

        # ID
        ex_id = c.get("recommend_session_id") or str(uuid.uuid4())

        return TrainingExample(
            example_id=ex_id,
            recommend_session_id=c.get("recommend_session_id"),
            user_id=c.get("user_id", "unknown"),
            doc_id=c.get("doc_id"),
            
            # Inputs
            context_embedding=embedding,
            input_context=d.get("input_sentence") if d else c.get("original_text"),
            
            # Scores
            reco_scores_vec=a.get("P_vec", {}),
            reco_scores_doc=a.get("P_doc", {}),
            reco_scores_rule=a.get("P_rule", {}),
            reco_options=reco_options,
            
            # Actions (B)
            executed_target_category=b.get("target_category") if b else None,
            executed_target_intensity=b.get("target_intensity") if b else None,
            executed_target_language=b.get("target_language") if b else None,
            llm_provider=b.get("llm_provider") if b else None,
            response_time_ms=b.get("response_time_ms") if b else None,
            
            # Labels (C/D)
            was_accepted=c.get("was_accepted", False),
            selected_option_index=c.get("index") if c.get("index") is not None else c.get("selected_option_index"),
            groundtruth_field=final_category,
            groundtruth_intensity=final_intensity,
            groundtruth_text=gt_text,
            
            match_metrics=match_metrics,
            consistency_flag="high",
            created_at=datetime.utcnow()
        )