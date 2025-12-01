from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

from dotenv import load_dotenv
from openai import AsyncOpenAI
from pymongo import MongoClient

from app.redis.client import set_macro_context
from app.schemas.macro import DocumentContextCache

load_dotenv()
_OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
_client: Optional[AsyncOpenAI] = None
if _OPENAI_API_KEY:
    _client = AsyncOpenAI(api_key=_OPENAI_API_KEY)

_MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
_MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "sentencify")
_mongo_client: Optional[MongoClient] = None

def _get_mongo_coll():
    global _mongo_client
    if _mongo_client is None:
        _mongo_client = MongoClient(_MONGO_URI)
    return _mongo_client[_MONGO_DB_NAME]["document_context_cache"]

_MODEL_NAME = "gpt-4.1-nano"

_JSON_REGEX = re.compile(r"\{.*\}", re.DOTALL)


def _extract_json_payload(text: str) -> dict[str, str]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned, flags=re.IGNORECASE).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()
    match = _JSON_REGEX.search(cleaned)
    if not match:
        raise ValueError("LLM response did not contain JSON payload")
    return json.loads(match.group(0))


async def analyze_and_cache_macro_context(
    doc_id: str, full_text: str
) -> Optional[DocumentContextCache]:
    if not full_text or len(full_text) < 10 or _client is None:
        return None

    if len(full_text) <= 3000:
        truncated_text = full_text
    else:
        head = full_text[:1500]
        tail = full_text[-1500:]
        truncated_text = f"{head}\n\n...[snipped middle part]...\n\n{tail}"

    prompt = (
        "Analyze the following text and extract the 'macro_topic' (short summary, max 30 words) "
        "and 'macro_category_hint' (one of: thesis, report, article, marketing, customer_service).\n"
        'Return ONLY a valid JSON object: {"topic": "...", "category": "..."}\n'
        f"Text: {truncated_text}"
    )

    response = await _client.chat.completions.create(
        model=_MODEL_NAME,
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt},
        ],
    )
    content = response.choices[0].message.content if response.choices else ""
    payload = _extract_json_payload(content or "")
    topic = payload.get("topic")
    category = payload.get("category")
    if not topic or not category:
        raise ValueError("LLM response missing topic/category fields")

    now = datetime.now(timezone.utc)
    cache_object = DocumentContextCache(
        doc_id=doc_id,
        macro_topic=topic,
        macro_category_hint=category,
        macro_llm_version=_MODEL_NAME,
        cache_hit_count=0,
        last_updated=now,
        valid_until=now + timedelta(hours=1),
    )
    await set_macro_context(doc_id, cache_object)
    
    # Sync to MongoDB for Dashboard/Persistence
    try:
        _get_mongo_coll().update_one(
            {"doc_id": doc_id},
            {"$set": cache_object.model_dump()},
            upsert=True
        )
    except Exception as e:
        print(f"[Macro] Failed to sync to Mongo: {e}")

    return cache_object
