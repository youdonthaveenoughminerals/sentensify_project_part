import os
import json
import sys
from pathlib import Path
from pymongo import MongoClient

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "api")))

# Configuration
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("MONGO_DB_NAME", "sentencify")
COLLECTION_NAME = "user_profile"

# Path to JSON data (Relative to project root when running via scripts)
# Assuming /app/data/import inside docker, or relative path locally
DATA_FILE_PATH = Path("/app/data/user_profile.json")

def import_user_profile():
    print(f"Connecting to MongoDB: {MONGO_URI}")
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    
    # 1. 컬렉션 확인 및 생성 (Optional: MongoDB creates on insert, but good for logs)
    if COLLECTION_NAME not in db.list_collection_names():
        print(f"Creating collection: {COLLECTION_NAME}")
        db.create_collection(COLLECTION_NAME)
    else:
        print(f"Collection {COLLECTION_NAME} already exists.")
        
    col = db[COLLECTION_NAME]

    # 2. 데이터 파일 확인
    target_file = DATA_FILE_PATH
    if not target_file.exists():
        # Fallback for local run (relative to project root)
        local_path = Path("data/user_profile.json")
        if local_path.exists():
            target_file = local_path
        else:
            print(f"❌ [Skip] Data file not found: {DATA_FILE_PATH} or {local_path}")
            return

    print(f"Reading data from {target_file}...")
    try:
        with open(target_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"❌ Error reading JSON: {e}")
        return

    if not data:
        print("⚠️ [Skip] JSON data is empty.")
        return

    print(f"Found {len(data)} records. Starting import...")

    count = 0
    for item in data:
        try:
            user_id = item.get("user_id")
            if not user_id:
                continue
            
            # Upsert based on user_id
            col.update_one(
                {"user_id": user_id},
                {"$set": item},
                upsert=True
            )
            count += 1
        except Exception as e:
            print(f"Error importing item: {e}")

    print(f"✅ Successfully imported {count} user profiles into '{COLLECTION_NAME}'.")

if __name__ == "__main__":
    import_user_profile()
