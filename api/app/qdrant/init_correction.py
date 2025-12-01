import json
import os
import uuid
from pathlib import Path
from datetime import datetime, timezone
from typing import List

from qdrant_client.models import PointStruct, VectorParams, Distance
from .client import get_qdrant_client
from app.utils.embedding import get_embedding

# Configuration
COLLECTION_NAME = "correction_history_v1"
VECTOR_SIZE = 768
BATCH_SIZE = 100

# Path to JSON data (Relative to project root when running via scripts)
# Assuming /app/data/import inside docker, or relative path locally
DATA_FILE_PATH = Path("/app/data/correction_history_embedded.json")

def init_correction_collection(client):
    """correction_history_v1 컬렉션을 초기화(재생성)합니다."""
    if client.collection_exists(COLLECTION_NAME):
        print(f"   🗑️  [Qdrant] Collection {COLLECTION_NAME} exists. Deleting for reset...")
        client.delete_collection(COLLECTION_NAME)
    
    print(f"   ✨ [Qdrant] Creating collection: {COLLECTION_NAME}")
    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
    )

def parse_mongo_oid(value):
    """Handle MongoDB Extended JSON $oid format"""
    if isinstance(value, dict) and "$oid" in value:
        return str(value["$oid"])
    return str(value) if value else "anonymous"

def parse_mongo_date(value):
    """Handle MongoDB Extended JSON $date format"""
    if isinstance(value, dict) and "$date" in value:
        return value["$date"]
    return value or datetime.now(timezone.utc).isoformat()

def insert_correction_history_data():
    """JSON 파일을 읽어 Qdrant에 적재합니다."""
    client = get_qdrant_client()
    
    # 1. 컬렉션 초기화 (Reset)
    init_correction_collection(client)

    # 2. 데이터 파일 확인
    target_file = DATA_FILE_PATH
    if not target_file.exists():
        # Fallback for local run
        local_path = Path("data/correction_history_embedded.json")
        if local_path.exists():
            target_file = local_path
        else:
            print(f"⚠️  [Skip] Data file not found: {DATA_FILE_PATH} or {local_path}")
            return

    print(f"   📥 [Read] Reading data from {target_file}...")
    try:
        with open(target_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"❌ Error reading JSON: {e}")
        return

    if not data:
        print("⚠️  [Skip] JSON data is empty.")
        return

    print(f"   🚀 [Load] Found {len(data)} records. Starting upsert...")

    points = []
    total_upserted = 0

    for i, item in enumerate(data):
        try:
            # Extract Fields with MongoDB Extended JSON parsing
            # Primary Key for Mapping: MongoDB _id -> Qdrant Point ID
            mongo_id_raw = item.get("_id")
            mongo_id_str = parse_mongo_oid(mongo_id_raw)
            
            # Create deterministic UUID from Mongo ID string
            point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, mongo_id_str))

            user_id = parse_mongo_oid(item.get("user"))
            created_at = parse_mongo_date(item.get("created_at"))
            
            original_sentence = item.get("input_sentence") or item.get("original_sentence")
            if not original_sentence:
                continue

            # Corrected Sentence Extraction
            corrected_sentence = None
            outputs = item.get("output_sentences", [])
            idx = item.get("selected_index")
            if isinstance(idx, int) and 0 <= idx < len(outputs):
                corrected_sentence = outputs[idx]
            elif outputs:
                corrected_sentence = outputs[0]

            # Payload Construction
            payload = {
                "mongo_id": mongo_id_str, # Store original ID in payload for reference
                "user_id": user_id,
                "original_sentence": original_sentence,
                "corrected_sentence": corrected_sentence,
                "intensity": item.get("intensity", "moderate"),
                "category": item.get("field") or item.get("category", "general"),
                "timestamp": created_at
            }

            # Vectorize Logic (Hybrid)
            # 1. Check if pre-computed vector exists in JSON
            if "vector" in item and isinstance(item["vector"], list) and len(item["vector"]) == VECTOR_SIZE:
                vector = item["vector"]
            else:
                # 2. Calculate embedding on the fly
                vector = get_embedding(original_sentence)

            # Point Construction
            points.append(PointStruct(id=point_id, vector=vector, payload=payload))

            # Batch Upsert
            if len(points) >= BATCH_SIZE:
                client.upsert(collection_name=COLLECTION_NAME, points=points)
                total_upserted += len(points)
                print(f"      -> Upserted batch ({total_upserted}/{len(data)})")
                points = []

        except Exception as e:
            print(f"      -> Error on item {i}: {e}")

    # Final Batch
    if points:
        client.upsert(collection_name=COLLECTION_NAME, points=points)
        total_upserted += len(points)
    
    print(f"✓ [Done] Total {total_upserted} records upserted to {COLLECTION_NAME}.")