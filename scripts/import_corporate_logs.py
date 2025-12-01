import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from pymongo import MongoClient, UpdateOne

# 환경 설정
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("MONGO_DB_NAME", "sentencify")

# 매핑 규칙 정의
INTENSITY_MAP = {
    "weak": "weak",
    "moderate": "moderate",
    "strong": "strong",
    # 기업 데이터에 있을 수 있는 다른 값들에 대한 매핑 (예시)
    "low": "weak",
    "medium": "moderate",
    "high": "strong",
    None: "moderate"
}

CATEGORY_MAP = {
    "thesis": "thesis",
    "email": "email",
    "article": "article",
    # 기업 데이터 필드값 매핑
    "academic": "thesis",
    "business": "email",
    "general": "article",
    None: "general"
}

def connect_db():
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    return db

def iso_from_timestamp(ts: float) -> str:
    """Unix timestamp (sec) -> ISO 8601 string"""
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()

def map_intensity(raw_value: Optional[str]) -> str:
    return INTENSITY_MAP.get(raw_value, "moderate")

def map_category(raw_value: Optional[str]) -> str:
    return CATEGORY_MAP.get(raw_value, "general")

def normalize_model_version(raw_value: Optional[str]) -> str:
    if not raw_value:
        return "unknown-model"
    # 예: "gpt-4" -> "gpt-4.1-nano" (간단한 예시)
    if "gpt-4" in raw_value:
        return "gpt-4.1-nano"
    return raw_value

def process_events(db):
    """
    event_raw 컬렉션에서 데이터를 읽어
    log_b_run, log_c_select 컬렉션으로 정규화하여 적재합니다.
    """
    raw_collection = db["event_raw"]
    
    # 타겟 컬렉션
    log_b_collection = db["log_b_run"]
    log_c_collection = db["log_c_select"]
    
    # 처리 카운터
    count_b = 0
    count_c = 0
    
    # Batch Ops
    ops_b = []
    ops_c = []
    
    cursor = raw_collection.find({})
    total_docs = raw_collection.count_documents({})
    print(f"[Importer] Found {total_docs} raw events.")

    for doc in cursor:
        event_name = doc.get("event")
        
        # 공통 필드 매핑
        user_id = doc.get("distinct_id") or "anonymous"
        # Time: Unix TS -> ISO
        raw_time = doc.get("time")
        created_at = iso_from_timestamp(raw_time) if isinstance(raw_time, (int, float)) else datetime.now(timezone.utc).isoformat()
        
        # Doc ID, Session ID 생성 (기업 데이터에 없으므로 임의 생성)
        # 동일 유저의 짧은 시간 내 이벤트라면 묶을 수도 있겠지만, 
        # MVP에서는 단순하게 랜덤 UUID 부여
        doc_id = str(uuid.uuid4())
        recommend_session_id = str(uuid.uuid4())
        insert_id = str(uuid.uuid4())

        if event_name == "event_editor_run_paraphrasing":
            # Map to Log B
            intensity = map_intensity(doc.get("maintenance"))
            category = map_category(doc.get("field"))
            model_version = normalize_model_version(doc.get("llm_name"))
            target_language = doc.get("target_language", "ko")
            
            log_entry = {
                "event": "editor_run_paraphrasing",
                "insert_id": insert_id,
                "recommend_session_id": recommend_session_id,
                "doc_id": doc_id,
                "user_id": user_id,
                
                "target_intensity": intensity,
                "target_category": category,
                "target_language": target_language,
                
                "paraphrase_llm_version": model_version,
                "paraphrase_llm_provider": doc.get("llm_provider", "openai"), # 신규 필드
                
                "input_sentence_length": len(doc.get("selected_text") or ""),
                "response_time_ms": doc.get("response_time_ms", 0),
                
                "created_at": created_at,
                "schema_version": "v2.4_migrated"
            }
            
            # 중복 방지: insert_id 기준 (여기서는 새로 생성하므로 의미 없지만, 원본 ID가 있다면 사용)
            # 원본의 insert_id가 있다면 그것을 사용
            if doc.get("insert_id"):
                log_entry["insert_id"] = doc.get("insert_id")
            
            ops_b.append(UpdateOne({"insert_id": log_entry["insert_id"]}, {"$set": log_entry}, upsert=True))
            count_b += 1

        elif event_name == "event_editor_selected_paraphrasing":
            # Map to Log C
            intensity = map_intensity(doc.get("maintenance"))
            category = map_category(doc.get("field"))
            target_language = doc.get("target_language", "ko")
            
            was_accepted = doc.get("was_accepted", False)
            selected_index = doc.get("index", -1)
            
            log_entry = {
                "event": "editor_selected_paraphrasing",
                "insert_id": insert_id,
                "recommend_session_id": recommend_session_id,
                "doc_id": doc_id,
                "user_id": user_id,
                
                "target_intensity": intensity, # C 로그에도 컨텍스트로 저장
                "target_category": category,
                "target_language": target_language,
                
                "was_accepted": was_accepted,
                "selected_option_index": selected_index,
                
                "created_at": created_at,
                "schema_version": "v2.4_migrated"
            }
            
            if doc.get("insert_id"):
                log_entry["insert_id"] = doc.get("insert_id")

            ops_c.append(UpdateOne({"insert_id": log_entry["insert_id"]}, {"$set": log_entry}, upsert=True))
            count_c += 1
            
        # Batch Execute
        if len(ops_b) >= 100:
            log_b_collection.bulk_write(ops_b)
            ops_b = []
        if len(ops_c) >= 100:
            log_c_collection.bulk_write(ops_c)
            ops_c = []

    # Flush remaining
    if ops_b:
        log_b_collection.bulk_write(ops_b)
    if ops_c:
        log_c_collection.bulk_write(ops_c)

    print(f"[Importer] Finished. Processed B: {count_b}, C: {count_c}")

if __name__ == "__main__":
    print("[Importer] Starting Corporate Log Migration...")
    db = connect_db()
    process_events(db)
