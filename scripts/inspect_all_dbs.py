import os
import redis
import time
from pymongo import MongoClient
from qdrant_client import QdrantClient

# Docker 내부 서비스명 기준
MONGO_URI = os.getenv("MONGO_URI", "mongodb://mongo:27017")
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
QDRANT_HOST = os.getenv("QDRANT_HOST", "qdrant")

def check_mongo():
    print("\n=== MongoDB Stats ===")
    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=2000)
        client.server_info() # Trigger connection
        dbs = client.list_database_names()
        print(f"Databases: {dbs}")
        for db_name in dbs:
            if db_name in ['admin', 'local', 'config']: continue
            db = client[db_name]
            print(f"  [DB: {db_name}]")
            cols = db.list_collection_names()
            if not cols:
                print("    (No collections)")
            for col_name in cols:
                count = db[col_name].count_documents({})
                print(f"    - {col_name}: {count} docs")
    except Exception as e:
        print(f"MongoDB Connection Failed: {e}")

def check_redis():
    print("\n=== Redis Stats ===")
    try:
        r = redis.Redis(host=REDIS_HOST, port=6379, decode_responses=True)
        r.ping()
        keys = r.keys("*")
        print(f"Total Keys: {len(keys)}")
        if keys:
            print("Sample Keys (up to 5):")
            for k in keys[:5]:
                t = r.type(k)
                print(f"  - {k} ({t})")
    except Exception as e:
        print(f"Redis Connection Failed: {e}")

def check_qdrant():
    print("\n=== Qdrant Stats ===")
    try:
        client = QdrantClient(host=QDRANT_HOST, port=6333)
        try:
            collections = client.get_collections()
            col_list = [c.name for c in collections.collections]
            print(f"Collections: {col_list}")
            for col_name in col_list:
                info = client.get_collection(col_name)
                print(f"  - {col_name}: {info.points_count} points, Status: {info.status}")
        except Exception:
             # Qdrant might be empty or not ready
             print("Qdrant is reachable, but failed to fetch collections (might be initializing).")
    except Exception as e:
        print(f"Qdrant Connection Failed: {e}")

if __name__ == "__main__":
    # Wait a bit for services to be fully ready
    time.sleep(2)
    check_mongo()
    check_redis()
    check_qdrant()
