import os
import time
from datetime import datetime, timezone
from pymongo import MongoClient
from elasticsearch import Elasticsearch, helpers

# --- Configuration ---
MONGO_URI = os.getenv("MONGO_URI", "mongodb://mongo:27017")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "sentencify")
ELASTICSEARCH_HOST = os.getenv("ELASTICSEARCH_HOST", "http://elasticsearch:9200")
SYNC_INTERVAL_SECONDS = 300  # 5 minutes

def get_mongo_client():
    return MongoClient(MONGO_URI)

def get_es_client():
    return Elasticsearch(ELASTICSEARCH_HOST)

def get_last_synced_at(es_client, index_pattern):
    """
    Queries Elasticsearch to find the maximum 'created_at' timestamp.
    Returns None if no data exists (implies full sync needed).
    """
    try:
        # Check if index exists first
        if not es_client.indices.exists(index=index_pattern):
            return None

        response = es_client.search(
            index=index_pattern,
            body={
                "size": 0,
                "aggs": {
                    "max_created_at": {
                        "max": {
                            "field": "created_at"
                        }
                    }
                }
            }
        )
        max_val_ms = response['aggregations']['max_created_at']['value']
        if max_val_ms:
            # ES returns epoch millis for date fields in aggregations? 
            # Actually, if the mapping is date, value_as_string is usually available.
            # Let's use value_as_string for safer ISO parsing or handle millis.
            
            val_str = response['aggregations']['max_created_at'].get('value_as_string')
            if val_str:
                # Parse ISO string to datetime object
                # Note: MongoDB expects datetime object for comparison
                try:
                    # Handle Z or +00:00
                    dt = datetime.fromisoformat(val_str.replace("Z", "+00:00"))
                    return dt
                except ValueError:
                    pass
            
            # Fallback to timestamp if string parse fails
            return datetime.fromtimestamp(max_val_ms / 1000.0, timezone.utc)
            
    except Exception as e:
        print(f"⚠️ Failed to get last checkpoint from ES: {e}")
        return None
    return None

def sync_golden_data(mongo_db, es_client):
    index_pattern = "sentencify-golden-*"
    target_index = f"sentencify-golden-{datetime.now().strftime('%Y.%m')}"
    
    last_synced_at = get_last_synced_at(es_client, index_pattern)
    
    query = {}
    if last_synced_at:
        print(f"[{datetime.now()}] Incremental Sync: Fetching data created after {last_synced_at}")
        query = {"created_at": {"$gt": last_synced_at}}
    else:
        print(f"[{datetime.now()}] Full Sync: No checkpoint found. Fetching all data.")

    collection = mongo_db["training_examples"]
    cursor = collection.find(query)
    
    actions = []
    count = 0

    for doc in cursor:
        count += 1
        # Convert ObjectId to string if present
        if "_id" in doc:
            doc["mongo_id"] = str(doc.pop("_id"))
        
        # Ensure datetime fields are ISO formatted
        if "created_at" in doc and isinstance(doc["created_at"], datetime):
            doc["created_at"] = doc["created_at"].isoformat()
            
        # Prepare Bulk Action
        action = {
            "_index": target_index,
            "_id": doc.get("example_id"), # Use example_id as ES Document ID
            "_source": doc
        }
        actions.append(action)

    if actions:
        success, failed = helpers.bulk(es_client, actions, stats_only=True)
        print(f"[{datetime.now()}] Synced {success} documents (Incremental). Failed: {failed}")
    else:
        print(f"[{datetime.now()}] No new documents found to sync.")

def main():
    print("Initializing Golden Data Sync Worker...")
    print(f"DEBUG: ELASTICSEARCH_HOST = {ELASTICSEARCH_HOST}")

    # Check connections first
    try:
        mongo_client = get_mongo_client()
        db = mongo_client[MONGO_DB_NAME]
        # Simple ping
        mongo_client.admin.command('ping')
        print("✅ MongoDB Connected")
    except Exception as e:
        print(f"❌ MongoDB Connection Failed: {e}")
        return

    try:
        es_client = get_es_client()
        print(f"DEBUG: ES Client Config: {es_client.transport.node_pool.all()}")
        
        if es_client.ping():
            print("✅ Elasticsearch Connected (Ping OK)")
            print(f"DEBUG: ES Info: {es_client.info()}")
        else:
            print("❌ Elasticsearch Connection Failed (Ping returned False)")
            # Try info anyway to see error
            try:
                print(f"DEBUG: Attempting info() despite ping fail: {es_client.info()}")
            except Exception as info_e:
                print(f"DEBUG: info() failed: {info_e}")
            return
    except Exception as e:
        print(f"❌ Elasticsearch Connection Error: {e}")
        return

    # Run Sync Loop
    while True:
        try:
            sync_golden_data(db, es_client)
        except Exception as e:
            print(f"⚠️ Error during sync: {e}")
        
        print(f"Sleeping for {SYNC_INTERVAL_SECONDS} seconds...")
        time.sleep(SYNC_INTERVAL_SECONDS)

if __name__ == "__main__":
    main()
