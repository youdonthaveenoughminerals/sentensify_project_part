import json
import os
from pathlib import Path
from typing import List, Dict, Any
from pymongo import MongoClient

# 설정
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("MONGO_DB_NAME", "sentencify")
DATA_DIR = Path("/data/import")  # 컨테이너 내부 경로 기준
# 로컬 테스트용 경로 (컨테이너 밖에서 실행 시)
if not DATA_DIR.exists():
    DATA_DIR = Path("data/import")

COLLECTION_NAME = "raw_corporate_data"

def connect_db():
    client = MongoClient(MONGO_URI)
    return client[DB_NAME]

def load_json_file(file_path: Path) -> List[Dict[str, Any]]:
    if not file_path.exists():
        print(f"[Warn] File not found: {file_path}")
        return []
    
    print(f"[Info] Loading {file_path}...")
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
            elif isinstance(data, dict):
                # 단일 객체인 경우 리스트로 감싸기 (혹시 모를 상황 대비)
                return [data]
            else:
                print(f"[Error] Unknown JSON format in {file_path}")
                return []
    except Exception as e:
        print(f"[Error] Failed to load {file_path}: {e}")
        return []

def import_raw_data():
    db = connect_db()
    collection = db[COLLECTION_NAME]
    
    # 기존 데이터 삭제 (재실행 시 중복 방지)
    deleted = collection.delete_many({})
    print(f"[Info] Cleared {deleted.deleted_count} documents from '{COLLECTION_NAME}'.")

    files_to_import = [
        "correction_history.json",
        "event_raw.json",
        # 필요한 경우 다른 파일 추가
    ]

    total_inserted = 0

    for filename in files_to_import:
        file_path = DATA_DIR / filename
        docs = load_json_file(file_path)
        
        if not docs:
            continue

        # 메타데이터 추가 (어느 파일에서 왔는지)
        for doc in docs:
            doc["_source_file"] = filename
        
        # Bulk Insert
        try:
            result = collection.insert_many(docs)
            count = len(result.inserted_ids)
            total_inserted += count
            print(f"[Info] Inserted {count} documents from {filename}")
        except Exception as e:
            print(f"[Error] Failed to insert documents from {filename}: {e}")

    print(f"✅ [Done] Total {total_inserted} documents imported into '{COLLECTION_NAME}'.")

if __name__ == "__main__":
    import_raw_data()
