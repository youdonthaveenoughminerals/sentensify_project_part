import os
import sys
from pymongo import MongoClient
from datetime import datetime

def main():
    # MongoDB Connection Config
    mongo_uri = os.getenv("MONGO_URI", "mongodb://mongo:27017")
    db_name = os.getenv("MONGO_DB_NAME", "sentencify")

    print(f"Connecting to MongoDB at: {mongo_uri} (DB: {db_name})")

    try:
        client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
        # Ping to verify connection
        client.admin.command('ping')
        db = client[db_name]
    except Exception as e:
        print(f"❌ Error connecting to MongoDB: {e}")
        sys.exit(1)

    # Collections to inspect
    collections = {
        "A (View)": "editor_recommend_options",
        "B (Run)": "editor_run_paraphrasing",
        "C (Accept)": "editor_selected_paraphrasing"
    }

    print("\n--- Data Freshness Report ---")
    
    for label, col_name in collections.items():
        col = db[col_name]
        try:
            count = col.count_documents({})
            latest = col.find_one(sort=[("created_at", -1)])
            
            print(f"\n[{label}] Collection: {col_name}")
            print(f"  Total Count: {count}")
            
            if latest:
                created_at = latest.get("created_at", "N/A")
                user_id = latest.get("user_id", "N/A")
                session_id = latest.get("recommend_session_id", "N/A")
                print(f"  Latest Doc:")
                print(f"    - Time: {created_at}")
                print(f"    - User: {user_id}")
                print(f"    - Session: {session_id}")
            else:
                print("  Latest Doc: (Collection is empty)")
                
        except Exception as e:
            print(f"  ❌ Error querying {col_name}: {e}")

    print("\n--- End of Report ---")

if __name__ == "__main__":
    main()
