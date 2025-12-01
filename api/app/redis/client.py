from __future__ import annotations

import json
import os
from typing import Optional

from redis.asyncio import Redis

from app.schemas.macro import DocumentContextCache

_redis_client: Optional[Redis] = None
_MACRO_CACHE_PREFIX = "macro_context:"


def _macro_key(doc_id: str) -> str:
    return f"{_MACRO_CACHE_PREFIX}{doc_id}"


def get_redis_client() -> Redis:
    """
    Return a singleton async Redis client configured via environment variables.
    """
    global _redis_client
    if _redis_client is not None:
        return _redis_client

    host = os.getenv("REDIS_HOST", "redis")
    port = int(os.getenv("REDIS_PORT", "6379"))
    db = int(os.getenv("REDIS_DB", "0"))
    password = os.getenv("REDIS_PASSWORD")

    _redis_client = Redis(
        host=host,
        port=port,
        db=db,
        password=password,
        decode_responses=True,
    )
    return _redis_client


async def set_macro_context(
    doc_id: str, data: DocumentContextCache, ttl: int = 3600
) -> None:
    """
    Persist Schema F payloads into Redis for later reuse.

    Args:
        doc_id: Document identifier and Redis key suffix.
        data: Macro context payload to store.
        ttl: Expiration time in seconds (default 1 hour).
    """
    client = get_redis_client()
    key = _macro_key(doc_id)
    payload = data.model_dump_json()
    await client.set(key, payload, ex=ttl)


async def get_macro_context(doc_id: str) -> Optional[DocumentContextCache]:
    """
    Load Schema F payloads from Redis.

    Returns:
        `DocumentContextCache` when found, otherwise `None`.
    """
    client = get_redis_client()
    key = _macro_key(doc_id)
    payload = await client.get(key)
    if payload is None:
        return None
    return DocumentContextCache.model_validate_json(payload)


async def set_llm_cache(key: str, candidates: list[str], ttl: int = 86400) -> None:
    """
    Cache LLM paraphrase candidates.
    TTL default: 24 hours (86400 seconds).
    """
    client = get_redis_client()
    payload = json.dumps(candidates, ensure_ascii=False)
    await client.set(key, payload, ex=ttl)


async def get_llm_cache(key: str) -> Optional[list[str]]:
    """
    Retrieve cached LLM paraphrase candidates.
    """
    client = get_redis_client()
    payload = await client.get(key)
    if payload is None:
        return None
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        return None
