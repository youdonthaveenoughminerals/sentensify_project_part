import logging
import uuid
from collections import Counter, defaultdict
from typing import List, Dict, Any, Tuple

from qdrant_client import QdrantClient
from qdrant_client.http import models
from pymongo.collection import Collection

# Constants
SEARCH_LIMIT_K = 10
QDRANT_COLLECTION_USER = "user_behavior_v1"
QDRANT_COLLECTION_HISTORY = "correction_history_v1"

logger = logging.getLogger("uvicorn")

def recommend_intensity(
    user_id: str, 
    context_vector: List[float], 
    qdrant_client: QdrantClient
) -> str:
    """
    Dual-Path Intensity Recommendation (User-Based + History-Based).
    
    Args:
        user_id: 사용자 ID
        context_vector: 현재 입력 문장의 임베딩 벡터 (768 dim)
        qdrant_client: Qdrant 연결 클라이언트
    Returns:
        final_intensity: 추천된 강도 (예: 'weak', 'moderate', 'strong')
    """
    
    # -------------------------------------------------------
    # 1. Path A: User-Based (P_user)
    # -------------------------------------------------------
    p_user = {'weak': 0.33, 'moderate': 0.34, 'strong': 0.33} # Default (Uniform)
    
    try:
        print("[Intensity_Rec] Entering Path A Try Block", flush=True)
        # Generate Qdrant Point ID from user_id (UUIDv5)
        # Must match the logic in SyncService
        user_point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, user_id))
        print(f"[Intensity_Rec] Generated Point ID for {user_id}: {user_point_id}", flush=True)
        
        user_points = qdrant_client.retrieve(
            collection_name=QDRANT_COLLECTION_USER,
            ids=[user_point_id],
            with_payload=["preferred_intensity_map"]
        )
        
        print(f"[Intensity_Rec] Retrieve Result: {user_points}", flush=True)
        
        if user_points:
            payload = user_points[0].payload or {}
            print(f"[Intensity_Rec] User Payload: {payload}", flush=True)
            
            pref_map = payload.get("preferred_intensity_map")
            if isinstance(pref_map, dict) and pref_map:
                # Normalize keys to ensure matching terms
                normalized_map = {}
                total_weight = 0.0
                for k, v in pref_map.items():
                    k_norm = k.lower().strip()
                    if k_norm in ['weak', 'moderate', 'strong']:
                        normalized_map[k_norm] = float(v)
                        total_weight += float(v)
                
                if total_weight > 0:
                    p_user = {k: v / total_weight for k, v in normalized_map.items()}
                    # Fill missing keys with 0.0
                    for k in ['weak', 'moderate', 'strong']:
                        p_user.setdefault(k, 0.0)
    except Exception as e:
        print(f"[Intensity_Rec] Path A (User) Error: {e}", flush=True)

    # -------------------------------------------------------
    # 2. Path B: History-Based (P_vec2)
    # -------------------------------------------------------
    p_vec2 = {'weak': 0.0, 'moderate': 0.0, 'strong': 0.0}
    found_count = 0
    
    try:
        search_result = qdrant_client.query_points(
            collection_name=QDRANT_COLLECTION_HISTORY,
            query=context_vector,
            limit=SEARCH_LIMIT_K,
            with_payload=["intensity"]
        ).points
        
        found_count = len(search_result)
        
        if found_count > 0:
            # Count frequencies
            intensity_counts = Counter()
            valid_hits = 0
            
            for hit in search_result:
                payload = hit.payload or {}
                intensity = payload.get("intensity")
                if intensity:
                    intensity = intensity.lower().strip()
                    if intensity in ['weak', 'moderate', 'strong']:
                        intensity_counts[intensity] += 1
                        valid_hits += 1
            
            if valid_hits > 0:
                p_vec2 = {
                    k: intensity_counts[k] / valid_hits 
                    for k in ['weak', 'moderate', 'strong']
                }
    except Exception as e:
        print(f"[Intensity_Rec] Path B (History) Error: {e}", flush=True)

    # -------------------------------------------------------
    # 3. Hybrid Calculation
    # -------------------------------------------------------
    final_scores = {}
    w_user = 0.4
    w_vec2 = 0.6
    
    # If P_vec2 is empty (Cold Start), rely 100% on P_user?
    # The prompt says: "Final_Score = (P_user * 0.4) + (P_vec2 * 0.6)"
    # But implies P_vec2 is 0s. 
    # However, typically if one path is cold, we might rebalance.
    # Strictly following prompt: P_vec2 is 0 if cold start.
    
    for k in ['weak', 'moderate', 'strong']:
        score = (p_user.get(k, 0.0) * w_user) + (p_vec2.get(k, 0.0) * w_vec2)
        final_scores[k] = round(score, 4)

    # Select Winner
    selected_intensity = max(final_scores, key=final_scores.get)

    # -------------------------------------------------------
    # 4. Logging
    # -------------------------------------------------------
    log_msg = (
        f"\n[Intensity_Rec] User_ID: {user_id}\n"
        f" - P_user (User Profile): {p_user}\n"
        f" - P_vec2 (Context Hist): {p_vec2} (Found: {found_count} items)\n"
        f" - Final Scores: {final_scores}\n"
        f" -> Selected: {selected_intensity}"
    )
    logger.info(log_msg)

    return selected_intensity