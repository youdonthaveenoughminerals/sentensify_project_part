from .client import get_qdrant_client
from qdrant_client.models import PointStruct
import ast 
from datetime import datetime, timezone
 

def insert_initial_data(df, start_id = 0):
    client = get_qdrant_client() 


    points = []

    for idx, (i,row) in enumerate(df.iterrows()) : 

        if isinstance(row["vec"], str) : 
            vector = ast.literal_eval(row["vec"])

        
        else : 
            vector = row["vec"]

        
        points.append(
            PointStruct(
                id = start_id + idx,
                vector = vector,
                payload = {
                    "context_hash": f"synthetic_{start_id + idx}",
                    "doc_id": row.get("doc_id", f"doc_synthetic_{idx}"),
                    "user_id": None,
                    "preview_text": row["content"][:100],
                    "field": row["field"],
                    "intensity": row.get("intensity", "moderate"),
                    "embedding_version": "v1.0",
                    "source_type": "synthetic",
                    "created_at": datetime.now(timezone.utc).isoformat()
                }
            )
        )
    
    client.upsert(
        collection_name = "context_block_v1",
        points = points
    )

  