from qdrant_client.models import VectorParams, Distance
from .client import get_qdrant_client

def create_collection():
    client = get_qdrant_client()

    client.recreate_collection(
        collection_name="context_block_v1",
        vectors_config=VectorParams(size=768, distance=Distance.COSINE)
    )