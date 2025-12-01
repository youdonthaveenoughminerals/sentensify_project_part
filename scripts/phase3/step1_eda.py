import os
import sys
import numpy as np
from pymongo import MongoClient
from collections import defaultdict

# Add project root to sys.path to import app modules correctly
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

try:
    from app.utils.embedding import get_embedding, embedding_service
except ImportError:
    print("❌ Failed to import embedding service. Make sure you are running this script from project root or api container.")
    print("   Try: docker-compose exec api python scripts/phase3/step1_eda.py")
    sys.exit(1)

# Config
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("MONGO_DB_NAME", "sentencify")

def run_eda():
    print("Loading Embedding Model...")
    embedding_service.load_model()
    print("✅ Model Loaded.")

    print(f"Connecting to MongoDB: {MONGO_URI}")
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    col = db["correction_history"]

    # 1. Fetch & Filter
    # selected_index != null AND selected_index is numeric
    query = {"selected_index": {"$ne": None, "$type": "number"}}
    cursor = col.find(query)
    
    docs = list(cursor)
    print(f"🔍 Found {len(docs)} accepted correction history records.")

    user_vectors = defaultdict(list)

    # 2. Extract & Embed
    for doc in docs:
        try:
            idx = doc.get("selected_index")
            outputs = doc.get("output_sentences", [])
            
            if idx is not None and 0 <= idx < len(outputs):
                final_sentence = outputs[idx]
                
                # User ID Extraction
                # correction_history.json structure shows "user": {"$oid": "..."} or "user": "string"
                # PyMongo converts $oid to ObjectId automatically
                user_field = doc.get("user")
                # Handle cases where 'user' is an ObjectId dict or a string ID
                if isinstance(user_field, dict) and '$oid' in user_field:
                    user_id = user_field['$oid']
                elif isinstance(user_field, str):
                    user_id = user_field
                elif user_field is None:
                    user_id = "anonymous"
                else:
                    user_id = str(user_field) # Fallback for other ObjectId types
                
                # 3. Generate Embedding
                vector = get_embedding(final_sentence)
                
                if vector:
                    user_vectors[user_id].append(vector)
                    
        except Exception as e:
            print(f"⚠️ Error processing doc {doc.get('_id')}: {e}")

    # 4. Mean Pooling
    print("\n📊 User Embedding Results (Mean Pooling):")
    print("-" * 50)
    
    for uid, vectors in user_vectors.items():
        if not vectors:
            continue
            
        # Convert to numpy array for easy mean calculation
        mat = np.array(vectors)
        mean_vec = np.mean(mat, axis=0)
        
        print(f"👤 User: {uid}")
        print(f"   - Accepted Sentences: {len(vectors)}")
        print(f"   - Vector Dimension: {mean_vec.shape[0]}")
        print(f"   - Sample (First 5 dims): {mean_vec[:5]}")
        print("-" * 50)

    print("✅ EDA Completed.")

if __name__ == "__main__":
    run_eda()