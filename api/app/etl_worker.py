import os
import time
import uuid
import logging
from datetime import datetime, timedelta, timezone
from apscheduler.schedulers.blocking import BlockingScheduler
from pymongo import MongoClient
from qdrant_client import QdrantClient
from qdrant_client.http.models import PointStruct, VectorParams, Distance

# Configuration
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("MONGO_DB_NAME", "sentencify")
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", 6333))
EMBED_DIM = int(os.getenv("EMBED_DIM", 768))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ETL_Worker")

def get_db():
    client = MongoClient(MONGO_URI)
    return client[DB_NAME]

def get_qdrant():
    return QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)

def sync_vectors():
    """
    [DISABLED] Syncs context_block (E) from Mongo to Qdrant.
    Reason: User requested to stop real-time sync for context_block.
    context_block_v1 is now populated only via initial load (train_data.csv).
    """
    # logger.info("Skipping sync_vectors (disabled by configuration).")
    pass

    # db = get_db()
    # q_client = get_qdrant()
    # collection_name = "context_block_v1" 

    # # Ensure Qdrant collection exists
    # try:
    #     q_client.get_collection(collection_name)
    # except Exception:
    #     logger.info(f"Creating Qdrant collection: {collection_name}")
    #     q_client.create_collection(
    #         collection_name=collection_name,
    #         vectors_config=VectorParams(size=EMBED_DIM, distance=Distance.COSINE),
    #     )

    # # Fetch pending documents
    # pending_docs = db["context_block"].find({"vector_synced": False}).limit(50)
    
    # count = 0
    # points = []
    # doc_ids_to_sync = []
    
    # from app.utils.embedding import get_embedding

    # for doc in pending_docs:
    #     try:
    #         # 1. Check Acceptance (Quality Gate)
    #         session_id = doc.get("recommend_session_id")
    #         is_accepted = False
    #         if session_id:
    #             accepted_c = db["editor_selected_paraphrasing"].find_one({
    #                 "recommend_session_id": session_id,
    #                 "was_accepted": True
    #             })
    #             if accepted_c:
    #                 is_accepted = True
            
    #         if is_accepted:
    #             text = doc.get("context_full")
    #             if not text:
    #                 doc_ids_to_sync.append(doc["_id"])
    #                 continue
                
    #             vector = get_embedding(text) 
                
    #             payload = {
    #                 "doc_id": doc.get("doc_id"),
    #                 "user_id": doc.get("user_id"),
    #                 "context_hash": doc.get("context_hash"),
    #                 "content": text,
    #                 "field": doc.get("field", "general"),
    #                 "intensity": accepted_c.get("target_intensity") or "moderate"
    #             }
                
    #             point_id = doc.get("insert_id")
    #             points.append(PointStruct(id=point_id, vector=vector, payload=payload))
    #             doc_ids_to_sync.append(doc["_id"])
    #             count += 1
    #         else:
    #             doc_ids_to_sync.append(doc["_id"]) # Skip but mark synced

    #     except Exception as e:
    #         logger.error(f"Error processing doc {doc.get('_id')}: {e}")

    # if points:
    #     try:
    #         q_client.upsert(collection_name=collection_name, points=points)
    #         logger.info(f"Synced {count} accepted vectors to Qdrant.")
    #     except Exception as e:
    #         logger.error(f"Failed to upsert to Qdrant: {e}")
    #         return 

    # if doc_ids_to_sync:
    #     db["context_block"].update_many(
    #         {"_id": {"$in": doc_ids_to_sync}},
    #         {"$set": {"vector_synced": True}}
    #     )

def sync_correction_history_weekly():
    """
    Weekly Sync for Correction History (D -> Qdrant).
    Logic:
      - Filter correction_history where vector_synced=False
      - Embed & Upsert to Qdrant correction_history_v1
      - Mark vector_synced=True
    """
    logger.info("Starting Weekly Correction History Sync...")
    db = get_db()
    q_client = get_qdrant()
    collection_name = "correction_history_v1"

    try:
        q_client.get_collection(collection_name)
    except Exception:
        logger.info(f"Creating Qdrant collection: {collection_name}")
        q_client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=EMBED_DIM, distance=Distance.COSINE),
        )

    # Process in batches
    batch_size = 100
    total_processed = 0
    
    from app.utils.embedding import get_embedding

    while True:
        pending_docs = list(db["correction_history"].find({"vector_synced": False}).limit(batch_size))
        if not pending_docs:
            break
            
        points = []
        doc_ids_to_sync = [] 

        for doc in pending_docs:
            try:
                original_sentence = doc.get("input_sentence") or doc.get("original_sentence")
                if not original_sentence:
                    doc_ids_to_sync.append(doc["_id"])
                    continue

                # Check if vector already exists (unlikely for new events, but safe check)
                if "vector" in doc and isinstance(doc["vector"], list) and len(doc["vector"]) == EMBED_DIM:
                    vector = doc["vector"]
                else:
                    # Calculate embedding (This is the main purpose of this worker)
                    vector = get_embedding(original_sentence)

                # Parse User ID
                user_data = doc.get("user")
                user_id = "anonymous"
                if isinstance(user_data, dict) and "$oid" in user_data:
                    user_id = str(user_data["$oid"])
                elif user_data:
                    user_id = str(user_data)

                # Parse Timestamp
                ts_data = doc.get("created_at")
                timestamp = datetime.now(timezone.utc).isoformat()
                if isinstance(ts_data, dict) and "$date" in ts_data:
                    timestamp = ts_data["$date"]
                elif ts_data:
                    timestamp = str(ts_data)

                corrected_sentence = None
                outputs = doc.get("output_sentences", [])
                idx = doc.get("selected_index")
                if isinstance(idx, int) and 0 <= idx < len(outputs):
                    corrected_sentence = outputs[idx]
                elif outputs:
                    corrected_sentence = outputs[0]

                payload = {
                    "mongo_id": str(doc["_id"]), # Store original ID
                    "user_id": user_id,
                    "original_sentence": original_sentence,
                    "corrected_sentence": corrected_sentence,
                    "intensity": doc.get("intensity", "moderate"),
                    "category": doc.get("field") or doc.get("category", "general"),
                    "timestamp": timestamp
                }

                # Use deterministic UUID based on MongoDB _id
                # This ensures mapping between Mongo and Qdrant
                point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, str(doc["_id"])))
                
                points.append(PointStruct(id=point_id, vector=vector, payload=payload))
                doc_ids_to_sync.append(doc["_id"])

            except Exception as e:
                logger.error(f"Error processing correction_history doc {doc.get('_id')}: {e}")

        if points:
            try:
                q_client.upsert(collection_name=collection_name, points=points)
                total_processed += len(points)
            except Exception as e:
                logger.error(f"Failed batch upsert: {e}")
                # Do not mark as synced
                continue

        if doc_ids_to_sync:
            db["correction_history"].update_many(
                {"_id": {"$in": doc_ids_to_sync}},
                {"$set": {"vector_synced": True}}
            )
    
    logger.info(f"Weekly Correction History Sync Completed. Processed {total_processed} items.")

from app.services.profile_service import ProfileService
from app.services.sync_service import SyncService
from app.services.etl_service import EtlService

def process_training_ops():
    """
    Fast-track ETL for Profile Updates
    """
    db = get_db()
    q_client = get_qdrant()
    
    behavior_coll = "user_behavior_v1"
    try:
        q_client.get_collection(behavior_coll)
    except Exception:
        logger.info(f"Creating Qdrant collection: {behavior_coll}")
        q_client.create_collection(
            collection_name=behavior_coll,
            vectors_config=VectorParams(size=EMBED_DIM, distance=Distance.COSINE),
        )

    profile_service = ProfileService(mongo_client=db.client)
    sync_service = SyncService(mongo_client=db.client, qdrant_client=q_client)
    
    pending_b = db["editor_run_paraphrasing"].find({"processed_for_training": {"$ne": True}}).limit(50)
    
    processed_ids = []
    users_to_update = set()
    
    for doc in pending_b:
        try:
            processed_ids.append(doc["_id"])
            if doc.get("user_id"):
                users_to_update.add(doc.get("user_id"))
        except Exception as e:
            logger.error(f"Error processing B-log {doc.get('_id')}: {e}")

    for uid in users_to_update:
        try:
            profile_service.update_user_profile(uid)
            sync_service.sync_user_to_qdrant(uid)
        except Exception as e:
            logger.error(f"Failed profile update/sync for {uid}: {e}")

    if processed_ids:
        db["editor_run_paraphrasing"].update_many(
            {"_id": {"$in": processed_ids}},
            {"$set": {"processed_for_training": True}}
        )

def run_etl_job():
    """
    Run the core ETL pipeline to generate H (Training Examples).
    Scheduled: Weekly (Saturday 03:00 UTC)
    """
    try:
        logger.info("Starting Weekly ETL Job...")
        etl_service = EtlService()
        count = etl_service.run_etl_pipeline(limit=1000)
        logger.info(f"Weekly ETL Job Completed. Processed {count} sessions.")
    except Exception as e:
        logger.error(f"Weekly ETL Job Failed: {e}")

def start_scheduler():
    scheduler = BlockingScheduler()
    interval = int(os.getenv("ETL_INTERVAL_SECONDS", 5))
    
    # 1. Real-time Sync
    scheduler.add_job(sync_vectors, 'interval', seconds=interval)
    scheduler.add_job(process_training_ops, 'interval', seconds=interval)
    
    # 2. Weekly Sync: Correction History (Every Sunday 04:00 UTC)
    scheduler.add_job(sync_correction_history_weekly, 'cron', day_of_week='sun', hour=4, minute=0)
    
    # 3. Weekly Training Data Gen (Every Saturday 03:00 UTC)
    scheduler.add_job(run_etl_job, 'cron', day_of_week='sat', hour=3, minute=0)
    
    logger.info(f"Starting ETL Worker Scheduler (RT Interval: {interval}s, Weekly Jobs Set)...")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        pass

if __name__ == "__main__":
    from app.utils.embedding import embedding_service
    logger.info("Loading embedding model for Worker...")
    embedding_service.load_model()
    
    start_scheduler()
