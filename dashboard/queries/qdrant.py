import os
import streamlit as st
from qdrant_client import QdrantClient
from typing import List, Dict, Any, Tuple

def get_qdrant_client() -> QdrantClient:
    """Returns a cached Qdrant client instance."""
    host = os.getenv("QDRANT_HOST", "qdrant")
    port = int(os.getenv("QDRANT_PORT", 6333))
    # Use st.cache_resource to share the client across re-runs
    # Note: In a real container setup, 'localhost' from dashboard container won't reach 'qdrant' container unless mapped or same net.
    # Dashboard is in same compose network, so 'qdrant' hostname should work.
    return QdrantClient(host=host, port=port)

@st.cache_data(ttl=60)
def get_collections() -> List[str]:
    """Fetches list of all collection names."""
    try:
        client = get_qdrant_client()
        collections = client.get_collections()
        return [c.name for c in collections.collections]
    except Exception as e:
        st.error(f"Failed to connect to Qdrant: {e}")
        return []

@st.cache_data(ttl=60)
def get_collection_info(collection_name: str) -> Dict[str, Any]:
    """Fetches detailed info about a collection."""
    try:
        client = get_qdrant_client()
        info = client.get_collection(collection_name)
        return {
            "status": info.status.name,
            "vectors_count": info.vectors_count,
            "points_count": info.points_count,
            "segments_count": info.segments_count,
            "config": info.config.model_dump()
        }
    except Exception:
        return {}

@st.cache_data(ttl=60)
def scroll_points(collection_name: str, limit: int = 100) -> List[Any]:
    """
    Scrolls points from a collection.
    Returns a list of Record objects (id, vector, payload).
    """
    try:
        client = get_qdrant_client()
        # Scroll returns (points, next_page_offset)
        points, _ = client.scroll(
            collection_name=collection_name,
            limit=limit,
            with_payload=True,
            with_vectors=True
        )
        return points
    except Exception as e:
        st.error(f"Error scrolling points: {e}")
        return []
