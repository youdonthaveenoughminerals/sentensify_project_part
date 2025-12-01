import os
from qdrant_client import QdrantClient

QDRANT_HOST = os.getenv("QDRANT_HOST", "qdrant")
QDRANT_PORT = 6333

def inspect_collections():
    try:
        client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
        collections = client.get_collections()
        print(f"=== Qdrant Collections ({len(collections.collections)}) ===")
        for col in collections.collections:
            print(f"- {col.name}")
            info = client.get_collection(col.name)
            print(f"  * Points: {info.points_count}")
            print(f"  * Status: {info.status}")
            print(f"  * Vector Size: {info.config.params.vectors.size if info.config.params.vectors else 'N/A'}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    inspect_collections()
