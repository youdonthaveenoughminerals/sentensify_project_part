import uuid
import logging
from typing import Dict, List, Optional, Any
from pymongo import MongoClient
from qdrant_client import QdrantClient
from qdrant_client.http.models import PointStruct

# Use shared client getters if available, or init here
# To avoid circular imports, we'll accept clients in init or use generic connection
logger = logging.getLogger("SyncService")

# Vector Dimensions (Must match Qdrant config)
DIM_CATEGORY = 7
DIM_STRENGTH = 3
DIM_LANGUAGE = 5
TOTAL_DIM = DIM_CATEGORY + DIM_STRENGTH + DIM_LANGUAGE
COLLECTION_NAME = "user_behavior_v1"

class SyncService:
    def __init__(self, mongo_client: MongoClient, qdrant_client: QdrantClient):
        self.db = mongo_client["sentencify"] # or get from env
        self.q_client = qdrant_client
        self.users_col = self.db["user_profile"] # Updated from "users"

    def _get_vector_safe(self, data: Dict, key: str, expected_len: int) -> List[float]:
        """Helper to safely extract or pad vectors."""
        # In v2.4, we moved to Maps (Dicts). We need to convert Map -> Vector for Qdrant compatibility?
        # OR did we keep the vector fields in Schema G alongside Map?
        # Checking Schema G: it has 'preferred_category_map' AND 'user_embedding_v1'.
        # But the legacy 'preferred_category_vector' might be gone or empty.
        # The architecture says "Vector DB Hybrid". 
        # Step3 script used: preferred_category_vector (List).
        # ProfileService now produces: preferred_category_map (Dict).
        # We MUST convert Map -> Vector here to maintain the 15-dim vector contract for Qdrant.
        
        # Map to Vector Logic (Fixed Taxonomy)
        # This is a hardcoded assumption for MVP. Ideally, store taxonomy in DB.
        KNOWN_CATEGORIES = ["email", "report", "message", "wiki", "thesis", "article", "presentation"] # Example 7
        KNOWN_INTENSITIES = ["weak", "moderate", "strong"] # Example 3
        KNOWN_LANGUAGES = ["ko", "en", "jp", "zh", "es"] # Example 5
        
        val = data.get(key)
        
        if isinstance(val, list):
            # Legacy vector support
            vec = val
            if len(vec) < expected_len:
                return vec + [0.0] * (expected_len - len(vec))
            return vec[:expected_len]
            
        elif isinstance(val, dict):
            # Map to Vector conversion
            vec = [0.0] * expected_len
            
            if "category" in key:
                keys = KNOWN_CATEGORIES
            elif "strength" in key or "intensity" in key:
                keys = KNOWN_INTENSITIES
            elif "language" in key:
                keys = KNOWN_LANGUAGES
            else:
                return vec # Unknown map type
                
            for i, k in enumerate(keys):
                vec[i] = val.get(k, 0.0)
            return vec
            
        return [0.0] * expected_len

    def sync_user_to_qdrant(self, user_id: str) -> bool:
        """
        Reads user profile from Mongo and upserts to Qdrant.
        Returns True if successful.
        """
        try:
            user_doc = self.users_col.find_one({"user_id": user_id})
            if not user_doc:
                print(f"[Sync] User {user_id} not found in Mongo.", flush=True)
                return False

            # Generate UUID
            try:
                point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, user_id))
            except Exception:
                point_id = str(uuid.uuid4())

            # Construct Vector (15-dim)
            # Note: ProfileService now saves 'preferred_category_map' etc.
            # We map them to vectors.
            vec_cat = self._get_vector_safe(user_doc, "preferred_category_map", DIM_CATEGORY)
            vec_str = self._get_vector_safe(user_doc, "preferred_intensity_map", DIM_STRENGTH)
            # Language might be missing in map, default to [1,0,0,0,0] (Ko) or zeros
            # ProfileService didn't save language map yet.
            vec_lang = [1.0, 0.0, 0.0, 0.0, 0.0] 
            
            full_vector = vec_cat + vec_str + vec_lang

            # Construct Payload
            payload = {
                "user_id": user_id,
                "recommend_accept_rate": user_doc.get("overall_accept_rate", 0.0),
                "paraphrase_execution_count": user_doc.get("paraphrase_execution_count", 0),
                # Store maps in payload for easy retrieval by Recommendation Service
                "preferred_category_map": user_doc.get("preferred_category_map"),
                "preferred_intensity_map": user_doc.get("preferred_intensity_map"),
            }
            
            # Use 15-dim Preference Vector
            # BERT Vector (768) is not used for the main vector in 'user_behavior_v1' (which is 15-dim).
            
            # Upsert
            self.q_client.upsert(
                collection_name=COLLECTION_NAME,
                points=[PointStruct(
                    id=point_id, 
                    vector=full_vector, 
                    payload=payload
                )]
            )
            print(f"[Sync] Synced user {user_id} to Qdrant (Vector 15-dim).", flush=True)
            return True

        except Exception as e:
            print(f"[Sync] Sync failed for {user_id}: {e}", flush=True)
            return False
