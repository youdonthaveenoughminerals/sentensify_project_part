import logging
import os
from typing import Any, Dict
from pymongo import MongoClient
from datetime import datetime, timezone

# MongoDB Connection Setup
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("MONGO_DB_NAME", "sentencify")

try:
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
except Exception as e:
    logging.error(f"Failed to connect to MongoDB: {e}")
    db = None

# Collection mapping
COLLECTIONS = {
    "editor_recommend_options": "editor_recommend_options",
    "editor_run_paraphrasing": "editor_run_paraphrasing",
    "editor_selected_paraphrasing": "editor_selected_paraphrasing",
    "context_block": "context_block",
    "recommend_log": "recommend_log",
    "editor_document_snapshot": "full_document_store",  # Map snapshot to full doc store logic later or raw
    "document_context_cache": "document_context_cache"
}

class MongoLogger:
    @staticmethod
    def log_event(collection_name: str, payload: Dict[str, Any]):
        """
        Inserts a log event directly into MongoDB.
        Intended to be used with FastAPI BackgroundTasks.
        """
        if db is None:
            logging.error("MongoDB client is not initialized. Log lost.")
            return

        try:
            target_col = COLLECTIONS.get(collection_name, collection_name)
            
            # Ensure created_at exists
            if "created_at" not in payload:
                payload["created_at"] = datetime.now(timezone.utc)
            
            # Special Handling for Document Snapshot -> Upsert logic could be here, 
            # but for "Logger" pattern, we just insert raw or handle specific update logic.
            # For Phase 2.4 simplified ELT, let's just insert raw events if it's a log, 
            # or update state if it's a document.
            
            if collection_name == "editor_document_snapshot":
                # K Event Logic: Update Full Document Store
                doc_id = payload.get("doc_id")
                if doc_id:
                    db["full_document_store"].update_one(
                        {"doc_id": doc_id},
                        {"$set": {
                            "latest_full_text": payload.get("full_text"),
                            "last_synced_at": payload.get("created_at"),
                            # We might calculate diff here or leave it to ETL
                        }},
                        upsert=True
                    )
            elif collection_name == "editor_selected_paraphrasing":
                # C Event Logic: Insert Log + Create Correction History
                db[target_col].insert_one(payload)
                
                if payload.get("was_accepted"):
                    history_payload = {
                        "user": payload.get("user_id"),
                        "correction_history_id": payload.get("correction_history_id"),
                        "created_at": payload.get("created_at"),
                        # Other fields would need to be enriched or passed in payload
                    }
                    db["correction_history"].insert_one(history_payload)
            
            else:
                # Standard Insert
                db[target_col].insert_one(payload)
                
        except Exception as e:
            logging.error(f"Error logging to {collection_name}: {e}")
