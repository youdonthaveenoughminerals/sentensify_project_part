import os
import json
import time
import sys
from pymongo import MongoClient
from pathlib import Path
from bson import json_util # MongoDB Extended JSON 처리를 위해 필요

# Configuration
MONGO_URI = os.getenv("MONGO_URI", "mongodb://mongo:27017")
DB_NAME = os.getenv("MONGO_DB_NAME", "sentencify")

# Data Paths
DATA_DIR_IMPORT = Path("/app/data/import")
DATA_DIR_ROOT = Path("/app/data")

def get_db_client():
    return MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)

def reset_collection(db, collection_name):
    """컬렉션이 존재하면 삭제(Drop)합니다."""
    if collection_name in db.list_collection_names():
        db[collection_name].drop()
        print(f"   🗑️  Dropped existing collection: '{collection_name}'")

def load_data_from_file(file_path):
    """
    JSON 또는 JSONL 파일을 읽어서 파이썬 리스트로 반환합니다.
    bson.json_util을 사용하여 $oid, $date 등을 자동으로 변환합니다.
    """
    try:
        # 1. Try standard JSON (Array)
        with open(file_path, "r", encoding="utf-8") as f:
            return json_util.loads(f.read())
    except json.JSONDecodeError:
        # 2. Try JSONL (Line-delimited)
        data = []
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        data.append(json_util.loads(line))
                    except Exception:
                        continue # Skip invalid lines
        if data:
            return data
        else:
            # 진짜 에러인 경우
            raise

def import_json(db, collection_name, file_path):
    """파일을 읽어 컬렉션에 적재합니다."""
    # 1. 초기화 (Drop)
    reset_collection(db, collection_name)

    # 2. 파일 확인
    if not file_path.exists():
        # 로컬 실행 시 경로 호환성 (fallback)
        local_path = Path(str(file_path).replace("/app/", ""))
        if local_path.exists():
            file_path = local_path
        else:
            print(f"⚠️  File not found: {file_path}. Skipping '{collection_name}'.")
            return

    print(f"📥 Importing {file_path.name} -> '{collection_name}'...")
    try:
        # 데이터 로드 (JSON or JSONL + BSON Parsing)
        data = load_data_from_file(file_path)
        
        if not data:
            print("   ⚠️  Data is empty.")
            return

        # 리스트가 아니면 리스트로 감싸기
        if isinstance(data, dict):
            data = [data]

        # 데이터 전처리
        if collection_name == "correction_history":
            for item in data:
                item["vector_synced"] = True
                # Remove vector field to save space in Mongo
                if "vector" in item:
                    del item["vector"]

        # Insert
        col = db[collection_name]
        if data:
            col.insert_many(data)
            print(f"   ✅ Imported {len(data)} documents.")
            
    except Exception as e:
        print(f"   ❌ Failed to import: {e}")

def main():
    print("⏳ [Mongo] Connecting to MongoDB...")
    client = None
    for i in range(30): # 최대 60초 대기
        try:
            client = get_db_client()
            client.admin.command('ping')
            print("✅ [Mongo] Connected successfully!")
            break
        except Exception:
            time.sleep(2)
            if i % 5 == 0:
                print(f"   ... waiting for Mongo ({i*2}s)")
    
    if not client:
        print("❌ [Mongo] Connection failed. Exiting.")
        sys.exit(1)

    db = client[DB_NAME]

    print("🚀 Starting Data Initialization (Drop & Import)...")

    # 1. Import Data (순서대로 진행)
    # Main Data
    import_json(db, "correction_history", DATA_DIR_ROOT / "correction_history_embedded.json")
    
    # User Data
    import_json(db, "user_profile", DATA_DIR_ROOT / "user_profile.json")
    
    # Meta/Log Data (Legacy/Archive) -> data/import/
    import_json(db, "usage_summary", DATA_DIR_IMPORT / "usage_summary.json")
    import_json(db, "client_properties", DATA_DIR_IMPORT / "client_properties.json")
    import_json(db, "event_raw", DATA_DIR_IMPORT / "event_raw.json")

    print("✨ [Mongo] Initialization Completed.")

if __name__ == "__main__":
    main()
