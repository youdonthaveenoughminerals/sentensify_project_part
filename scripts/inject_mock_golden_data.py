import os
import uuid
from datetime import datetime, timezone
from pymongo import MongoClient

# --- Configuration ---
MONGO_URI = os.getenv("MONGO_URI", "mongodb://mongo:27017")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "sentencify")

def get_mongo_collection(name: str):
    client = MongoClient(MONGO_URI)
    db = client[MONGO_DB_NAME]
    return db[name]

def inject_mock_data():
    print(f"Connecting to MongoDB at {MONGO_URI}...")
    col = get_mongo_collection("training_examples")
    
    mock_data = []
    for i in range(5):
        doc = {
            "example_id": str(uuid.uuid4()),
            "recommend_session_id": str(uuid.uuid4()),
            "user_id": f"mock_user_{i}",
            "doc_id": f"mock_doc_{i}",
            "context_embedding": [0.1 * i] * 8,
            "macro_category_hint": "email",
            "reco_category_input": "email",
            "reco_scores_vec": {"email": 0.9, "thesis": 0.1},
            "executed_target_language": "ko",
            "executed_target_intensity": "moderate",
            "executed_target_category": "email",
            "was_accepted": True,
            "selected_option_index": 0,
            "consistency_flag": "high",
            "created_at": datetime.now(timezone.utc),
            "schema_version": "v2.4"
        }
        mock_data.append(doc)

    result = col.insert_many(mock_data)
    print(f"✅ Successfully injected {len(result.inserted_ids)} mock documents into 'training_examples'.")

if __name__ == "__main__":
    inject_mock_data()
