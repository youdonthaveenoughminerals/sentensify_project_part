from __future__ import annotations

import os
import uuid
from typing import List

from pymongo import MongoClient
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct

from app.qdrant.client import get_qdrant_client

MONGO_URI = os.getenv("MONGO_URI", "mongodb://mongo:27017")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "sentencify")


def _get_mongo_collection(name: str, mongo_client: MongoClient | None = None):
    client = mongo_client or MongoClient(MONGO_URI)
    db = client[MONGO_DB_NAME]
    return db[name]


def migrate_vectors_to_qdrant(
    batch_size: int = 100,
    mongo_client: MongoClient | None = None,
    qdrant_client: QdrantClient | None = None,
) -> int:
    collection = _get_mongo_collection("training_examples", mongo_client)
    client = qdrant_client or get_qdrant_client()

    cursor = collection.find(
        {
            "consistency_flag": "high",
            "was_accepted": True,
            "groundtruth_field": {"$ne": None},
        }
    )

    batch: List[PointStruct] = []
    migrated = 0

    for row in cursor:
        example_id = row.get("example_id") or str(uuid.uuid4())
        vector = row.get("context_embedding") or []
        payload = {
            "field": row.get("groundtruth_field"),
            "doc_id": row.get("doc_id"),
            "user_id": row.get("user_id"),
            "source_type": "real_user",
            "original_created_at": row.get("created_at"),
        }
        batch.append(PointStruct(id=example_id, vector=vector, payload=payload))

        if len(batch) >= batch_size:
            client.upsert(collection_name="context_block_v1", points=batch)
            migrated += len(batch)
            batch = []

    if batch:
        client.upsert(collection_name="context_block_v1", points=batch)
        migrated += len(batch)

    return migrated
