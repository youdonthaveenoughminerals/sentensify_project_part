from typing import Optional, List, Dict, Any
from collections import Counter
from datetime import datetime
import numpy as np

from pymongo import MongoClient

from app.config import MONGO_URI, MONGO_DB_NAME
from app.schemas.profile import UserProfile
from app.services.logger import COLLECTIONS

class ProfileService:
    def __init__(self, mongo_client: Optional[MongoClient] = None):
        self.client = mongo_client or MongoClient(MONGO_URI)
        self.db = self.client[MONGO_DB_NAME]
        self.col_a = self.db["editor_recommend_options"]
        self.col_b = self.db["editor_run_paraphrasing"]
        self.col_c = self.db["editor_selected_paraphrasing"]
        self.col_d = self.db["correction_history"] 
        self.profile_col = self.db["user_profile"]

    def update_user_profile(self, user_id: str) -> Optional[UserProfile]:
        """
        Calculates user profile from A, B, C, D logs and upserts it to MongoDB.
        Robust against Cold Start (no existing profile or logs).
        """
        if not user_id:
            return None

        print(f"[Profile] Starting update for {user_id}...", flush=True)

        # 1. Initialize Defaults
        stats = {
            "total_recommend": 0,
            "total_runs": 0,
            "total_accepts": 0,
            "accept_rate": 0.0
        }
        preferences = {
            "category": {},
            "intensity": {}
        }
        user_embedding = []

        # 2. Aggregation (Source of Truth: Logs)
        try:
            # A. Count Recommendations
            stats["total_recommend"] = self.col_a.count_documents({"user_id": user_id})
            
            # B. Run Logs (Counts & Preferences)
            b_cursor = self.col_b.find({"user_id": user_id}, {"target_category": 1, "target_intensity": 1})
            b_docs = list(b_cursor)
            stats["total_runs"] = len(b_docs)
            
            if b_docs:
                cat_counts = Counter([d.get("target_category", "unknown") for d in b_docs if d.get("target_category")])
                int_counts = Counter([d.get("target_intensity", "unknown") for d in b_docs if d.get("target_intensity")])
                
                # Calculate Ratios
                if stats["total_runs"] > 0:
                    preferences["category"] = {k: v / stats["total_runs"] for k, v in cat_counts.items()}
                    preferences["intensity"] = {k: v / stats["total_runs"] for k, v in int_counts.items()}

            # C. Accept Logs
            stats["total_accepts"] = self.col_c.count_documents({"user_id": user_id, "was_accepted": True})
            
            if stats["total_runs"] > 0:
                stats["accept_rate"] = stats["total_accepts"] / stats["total_runs"]

            # D. Behavior Embedding
            # Query for D logs that have vector_synced=True
            d_cursor = self.col_d.find({
                "user_id": user_id, 
                "vector_synced": True,
                "context_embedding": {"$exists": True, "$ne": None, "$not": {"$size": 0}}
            }, {"context_embedding": 1})
            
            embeddings = [d.get("context_embedding") for d in d_cursor if d.get("context_embedding")]
            
            if embeddings:
                user_embedding = np.mean(embeddings, axis=0).tolist()
            
        except Exception as e:
            print(f"[Profile] Aggregation error for {user_id}: {e}", flush=True)
            # Continue with defaults if partial failure

        # 3. Construct & Save (Upsert)
        try:
            profile_data = UserProfile(
                user_id=user_id,
                total_recommend_count=stats["total_recommend"],
                total_accept_count=stats["total_accepts"],
                overall_accept_rate=stats["accept_rate"],
                paraphrase_execution_count=stats["total_runs"],
                accept_rate_by_feature={
                    "final_result": stats["accept_rate"],
                    "option_match": 0.0
                },
                preferred_category_map=preferences["category"],
                preferred_intensity_map=preferences["intensity"],
                user_embedding_v1=user_embedding,
                updated_at=datetime.utcnow()
            )
            
            # Update G
            self.profile_col.update_one(
                {"user_id": user_id},
                {"$set": profile_data.model_dump()},
                upsert=True
            )
            print(f"[Profile] Successfully updated profile for {user_id}", flush=True)
            return profile_data

        except Exception as e:
            print(f"[Profile] DB Upsert error for {user_id}: {e}", flush=True)
            return None