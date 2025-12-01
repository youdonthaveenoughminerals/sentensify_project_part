import json
import uuid
import os
from pathlib import Path
from typing import List, Dict, Any

from qdrant_client import QdrantClient
from qdrant_client.http.models import PointStruct, VectorParams, Distance

# 프로젝트 루트 (scripts/phase3/../..)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_FILE_PATH = PROJECT_ROOT / "data" / "user_profile.json"

# Qdrant 설정
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", 6333))
COLLECTION_NAME = "user_behavior_v1"

# Vector Dimensions
DIM_CATEGORY = 7
DIM_STRENGTH = 3
DIM_LANGUAGE = 5
TOTAL_DIM = DIM_CATEGORY + DIM_STRENGTH + DIM_LANGUAGE

def load_json_data(file_path: Path) -> List[Dict[str, Any]]:
    """Loads JSON data from the specified path."""
    if not file_path.exists():
        raise FileNotFoundError(f"Data file not found at: {file_path}")
    
    with file_path.open("r", encoding="utf-8") as f:
        return json.load(f)

def create_uuid_from_string(val: str) -> str:
    """Generates a consistent UUID from a string (e.g., MongoDB ObjectId)."""
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, val))

def get_vector_safe(data: Dict, key: str, expected_len: int) -> List[float]:
    """
    Retrieves a list of floats from the data. 
    Returns a zero-vector of `expected_len` if the key is missing or null.
    """
    vec = data.get(key)
    if vec is None or not isinstance(vec, list):
        return [0.0] * expected_len
    
    # Basic validation/padding could be added here if needed, 
    # but assuming input integrity or truncation for now based on prompt.
    # Enforcing length just in case:
    if len(vec) < expected_len:
        return vec + [0.0] * (expected_len - len(vec))
    return vec[:expected_len]

def main():
    # 1. Connect to Qdrant
    client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
    print(f"Connected to Qdrant at {QDRANT_HOST}:{QDRANT_PORT}")

    # 2. Initialize Collection
    if client.collection_exists(COLLECTION_NAME):
        client.delete_collection(COLLECTION_NAME)
        print(f"Deleted existing collection: {COLLECTION_NAME}")

    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(size=TOTAL_DIM, distance=Distance.COSINE),
    )
    print(f"Created collection: {COLLECTION_NAME} (Size: {TOTAL_DIM}, Distance: Cosine)")

    # 3. Process Data
    raw_data = load_json_data(DATA_FILE_PATH)
    points = []

    print(f"Processing {len(raw_data)} records from {DATA_FILE_PATH}...")

    for user_profile in raw_data:
        user_id_str = user_profile.get("user_id")
        if not user_id_str:
            print("Skipping record without user_id")
            continue

        # Generate consistent UUID
        point_id = create_uuid_from_string(user_id_str)

        # Construct Vector
        # Category (7) + Strength (3) + Language (5)
        vec_cat = get_vector_safe(user_profile, "preferred_category_vector", DIM_CATEGORY)
        vec_str = get_vector_safe(user_profile, "preferred_strength_vector", DIM_STRENGTH)
        vec_lang = get_vector_safe(user_profile, "preferred_language_vector", DIM_LANGUAGE)
        
        full_vector = vec_cat + vec_str + vec_lang

        # Construct Payload (exclude vector fields)
        payload = user_profile.copy()
        keys_to_exclude = [
            "preferred_category_vector",
            "preferred_strength_vector",
            "preferred_language_vector"
        ]
        for k in keys_to_exclude:
            payload.pop(k, None)

        # Create Point
        points.append(PointStruct(
            id=point_id,
            vector=full_vector,
            payload=payload
        ))

    # 4. Upload (Batch Upsert)
    if points:
        client.upsert(
            collection_name=COLLECTION_NAME,
            points=points
        )
        print(f"✅ 총 {len(points)}명의 유저 프로필이 Qdrant에 적재되었습니다.")
    else:
        print("⚠️ 적재할 데이터가 없습니다.")

if __name__ == "__main__":
    main()
