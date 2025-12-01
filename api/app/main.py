import hashlib
import json
import os
import traceback
import time # Added missing import
from pathlib import Path
from typing import Any, Dict, List, Optional
import uuid
from datetime import datetime, timezone

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pymongo import MongoClient
from dotenv import load_dotenv
from openai import AsyncOpenAI
from .auth import auth_router

from app.prompts import build_paraphrase_prompt
from app.qdrant.service import compute_p_vec
from app.redis.client import get_macro_context, get_llm_cache, set_llm_cache
from app.services.macro_service import analyze_and_cache_macro_context
from app.services.classifier_service import ClassifierService
from app.services.logger import MongoLogger
from app.utils.embedding import get_embedding, embedding_service
from app.utils.scoring import calculate_alpha, calculate_maturity_score
from collections import defaultdict
from app.services.recommendation_service import recommend_intensity
from app.qdrant.client import get_qdrant_client

load_dotenv()

class RecommendRequest(BaseModel):
    doc_id: str
    user_id: str
    selected_text: str
    context_prev: Optional[str] = None
    context_next: Optional[str] = None
    field: Optional[str] = None
    language: Optional[str] = None
    intensity: Optional[str] = None
    user_prompt: Optional[str] = None
    dev_mode: Optional[bool] = False


class RecommendOption(BaseModel):
    category: str
    language: str
    intensity: str
    user_prompt: Optional[str] = None


class RecommendResponse(BaseModel):
    insert_id: str
    recommend_session_id: str
    reco_options: list[RecommendOption]
    recommended_intensity: Optional[str] = None
    P_rule: Dict[str, float]
    P_vec: Dict[str, float]
    P_doc: Dict[str, float]
    doc_maturity_score: float
    applied_weight_doc: float
    context_hash: str
    model_version: str
    api_version: str
    schema_version: str
    embedding_version: str


class ParaphraseRequest(BaseModel):
    doc_id: str
    user_id: str
    selected_text: str
    context_prev: Optional[str] = None
    context_next: Optional[str] = None
    category: Optional[str] = "general"
    language: Optional[str] = "ko"
    intensity: Optional[str] = "moderate"
    user_prompt: Optional[str] = None
    recommend_session_id: Optional[str] = None
    source_recommend_event_id: Optional[str] = None
    selected_reco_option_index: Optional[int] = None
    is_custom_option: Optional[bool] = None


class ParaphraseResponse(BaseModel):
    candidates: List[str]
    history_id: Optional[str] = None


class LogRequest(BaseModel):
    event: str

    class Config:
        extra = "allow"


class CreateDocumentRequest(BaseModel):
    user_id: str


class UpdateDocumentRequest(BaseModel):
    latest_full_text: str
    user_id: str


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

LOG_DIR = Path("logs")
MONGO_URI = os.getenv("MONGO_URI", "mongodb://mongo:27017")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "sentencify")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
_openai_client: AsyncOpenAI | None = AsyncOpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None
if OPENAI_API_KEY:
    print("[OpenAI] API key loaded from environment.")
else:
    print("[OpenAI] API key not found; paraphrase endpoint will use fallbacks.")

_mongo_client: MongoClient | None = None
_classifier_service: ClassifierService | None = None

@app.on_event("startup")
def startup_event():
    '''임베딩 모델 및 분류기 로딩'''
    global _classifier_service
    print("Loading embedding model (klue/bert-base)")
    from app.utils.embedding import embedding_service
    embedding_service.load_model()
    print("Embedding model ready!")
    
    print("Loading KoBERT Classifier...")
    _classifier_service = ClassifierService()
    print("KoBERT Classifier ready!")


def get_mongo_collection(name: str):
    global _mongo_client
    if _mongo_client is None:
        _mongo_client = MongoClient(MONGO_URI)
    db = _mongo_client[MONGO_DB_NAME]
    return db[name]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_context_full(prev: Optional[str], selected: str, next_: Optional[str]) -> str:
    selected = selected or ""
    context_parts = []
    if prev:
        context_parts.append(prev)
    if next_:
        context_parts.append(next_)

    if context_parts:
        context_str = " ".join(context_parts)
        return f"{selected}\n[Context] {context_str}"

    return selected

def build_context_hash(doc_id: str, context_full: str) -> str:
    payload = f"{doc_id}:{context_full}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

def _fallback_candidates(selected_text: str) -> List[str]:
    text = selected_text or ""
    return [text, text, text]

def _clean_candidates(raw_text: str, fallback: str) -> List[str]:
    cleaned: List[str] = []
    for line in raw_text.splitlines():
        candidate = line.strip()
        if not candidate:
            continue
        candidate = candidate.lstrip("0123456789.-•) ").strip()
        if candidate:
            cleaned.append(candidate)
    while len(cleaned) < 3:
        cleaned.append(fallback)
    return cleaned[:3]

def _normalize_for_cache(text: str) -> str:
    if not text:
        return ""
    return text.strip().rstrip(".,!?;:")

def append_jsonl(filename: str, payload: Dict) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    path = LOG_DIR / filename
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


@app.post("/recommend", response_model=RecommendResponse)
async def recommend(req: RecommendRequest, background_tasks: BackgroundTasks) -> RecommendResponse:
    start_time = time.time() # Start latency measurement
    insert_id = str(uuid.uuid4())
    recommend_session_id = str(uuid.uuid4())

    context_full = build_context_full(req.context_prev, req.selected_text, req.context_next)
    context_hash = build_context_hash(req.doc_id, context_full)
    
    try:
        macro_context = await get_macro_context(req.doc_id)
    except Exception as exc:
        print(f"[Redis] Failed to load macro context: {exc}", flush=True)
        traceback.print_exc()
        macro_context = None

    # Pre-calculate embedding for both Intensity and P_vec
    embedding: List[float] = []
    try:
        embedding = get_embedding(context_full)
    except Exception as e:
        print(f"[ERROR] Embedding generation failed: {e}", flush=True)
        traceback.print_exc()

    # [DEV MODE] Immediate Profile Update
    if req.dev_mode:
        print(f"[Dev] Triggering immediate profile update for user {req.user_id}")
        try:
            from app.services.profile_service import ProfileService
            # Use global mongo client if available
            ProfileService(mongo_client=_mongo_client).update_user_profile(req.user_id)
        except Exception as e:
            print(f"[Dev] Profile update failed: {e}")
            traceback.print_exc()

    # Intensity Recommendation (Personalization) - Hybrid P_user + P_vec2
    recommended_intensity = "moderate"
    try:
        q_client = get_qdrant_client()
        
        recommended_intensity = recommend_intensity(
            user_id=req.user_id,
            context_vector=embedding,
            qdrant_client=q_client
        )
    except Exception as e:
        print(f"[Recommend] Intensity recommendation failed: {e}")
        traceback.print_exc()
        recommended_intensity = "moderate" # Fallback

    # P_rule Calculation
    p_rule: Dict[str, float] = {}
    if _classifier_service:
        p_rule = _classifier_service.predict_p_rule(context_full)
    else:
        p_rule = {"thesis": 0.5, "report": 0.3, "article": 0.2}
    
    # P_vec (Category) Calculation using pre-calculated embedding
    p_vec: Dict[str, float] = {}
    try:
        if embedding:
            p_vec = compute_p_vec(embedding, limit=15)
        else:
            # Fallback if embedding failed earlier
            p_vec = {"thesis": 0.7, "report": 0.2, "article": 0.1}
    except Exception as e:
        print(f"[ERROR] P_vec calculation failed: {e}", flush=True)
        traceback.print_exc()
        p_vec = {"thesis": 0.7, "report": 0.2, "article": 0.1}

    p_doc: Dict[str, float] = {}
    if macro_context:
        p_doc[macro_context.macro_category_hint] = 1.0
    elif p_rule:
        best_rule_category = max(p_rule, key=p_rule.get)
        p_doc[best_rule_category] = 1.0

    doc_text_for_len = (req.context_prev or "") + (req.selected_text or "") + (req.context_next or "")
    doc_length = len(doc_text_for_len)
    doc_maturity = calculate_maturity_score(doc_length)
    alpha = calculate_alpha(doc_maturity)
    
    score_categories = set(p_vec) | set(p_doc)
    if not score_categories:
        score_categories = set(p_rule)

    W_VEC = 0.6
    W_RULE = 0.4
    
    final_scores: Dict[str, float] = {}
    for k in score_categories:
        score_doc = p_doc.get(k, 0.0)
        score_vec = p_vec.get(k, 0.0)
        score_rule = p_rule.get(k, 0.0)
        
        micro_score = (W_VEC * score_vec) + (W_RULE * score_rule)
        final_scores[k] = (alpha * score_doc) + ((1 - alpha) * micro_score)

    best_category = max(final_scores, key=final_scores.get)
    language = req.language or "ko"
    
    # Use requested intensity OR the recommended one
    intensity = req.intensity or recommended_intensity

    reco_options = [
        RecommendOption(
            category=best_category,
            language=language,
            intensity=intensity,
            user_prompt=None,
        )
    ]

    model_version = "phase1_stub_v1"
    api_version = "v1"
    schema_version = "phase1_aie_v1"
    embedding_version = "embed_v1_stub"

    # Calculate latency
    latency_ms = (time.time() - start_time) * 1000

    a_event = {
        "event": "editor_recommend_options",
        "insert_id": insert_id,
        "recommend_session_id": recommend_session_id,
        "doc_id": req.doc_id,
        "user_id": req.user_id,
        "selected_text": req.selected_text,
        "context_prev": req.context_prev,
        "context_next": req.context_next,
        "context_hash": context_hash,
        "context_full_preview": context_full[:500],
        "reco_options": [o.model_dump() for o in reco_options],
        "recommended_intensity": recommended_intensity, 
        "P_rule": p_rule,
        "P_vec": p_vec,
        "P_doc": p_doc,
        "doc_maturity_score": doc_maturity,
        "applied_weight_doc": alpha,
        "model_version": model_version,
        "api_version": api_version,
        "schema_version": schema_version,
        "embedding_version": embedding_version,
        "latency_ms": latency_ms, # Added
        "created_at": _now_iso(),
    }
    append_jsonl("a.jsonl", a_event)
    background_tasks.add_task(MongoLogger.log_event, "editor_recommend_options", a_event)

    i_event = {
        "event": "recommend_log",
        "insert_id": str(uuid.uuid4()),
        "source_recommend_event_id": insert_id,
        "recommend_session_id": recommend_session_id,
        "doc_id": req.doc_id,
        "user_id": req.user_id,
        "context_hash": context_hash,
        "P_rule": p_rule,
        "P_vec": p_vec,
        "P_doc": p_doc,
        "doc_maturity_score": doc_maturity,
        "applied_weight_doc": alpha,
        "model_version": model_version,
        "api_version": api_version,
        "schema_version": schema_version,
        "latency_ms": latency_ms, # Added
        "created_at": _now_iso(),
    }
    append_jsonl("i.jsonl", i_event)
    background_tasks.add_task(MongoLogger.log_event, "recommend_log", i_event)

    e_event = {
        "event": "context_block",
        "insert_id": str(uuid.uuid4()),
        "doc_id": req.doc_id,
        "user_id": req.user_id,
        "context_hash": context_hash,
        "context_full": context_full,
        "field": req.field or "general",
        "embedding_version": embedding_version,
        "vector_synced": False, # Flag for ETL Worker
        "created_at": _now_iso(),
    }
    append_jsonl("e.jsonl", e_event)
    background_tasks.add_task(MongoLogger.log_event, "context_block", e_event)

    return RecommendResponse(
        insert_id=insert_id,
        recommend_session_id=recommend_session_id,
        reco_options=reco_options,
        recommended_intensity=recommended_intensity,
        P_rule=p_rule,
        P_vec=p_vec,
        P_doc=p_doc,
        doc_maturity_score=doc_maturity,
        applied_weight_doc=alpha,
        context_hash=context_hash,
        model_version=model_version,
        api_version=api_version,
        schema_version=schema_version,
        embedding_version=embedding_version,
    )


@app.post("/paraphrase", response_model=ParaphraseResponse)
async def paraphrase(req: ParaphraseRequest, background_tasks: BackgroundTasks) -> ParaphraseResponse:
    fallback_text = req.selected_text or ""
    fallback_candidates = _fallback_candidates(fallback_text)
    category = req.category or "general"
    language = req.language or "ko"
    intensity = req.intensity or "moderate"
    event_id = str(uuid.uuid4())

    normalized_text = _normalize_for_cache(req.selected_text)
    raw_key = f"{normalized_text}|{category}|{intensity}|{language}|{req.user_prompt or ''}"
    cache_key = f"llm:para:{hashlib.sha256(raw_key.encode()).hexdigest()}"

    cached_candidates = await get_llm_cache(cache_key)
    if cached_candidates:
        b_event = {
            "event": "editor_run_paraphrasing",
            "event_id": event_id,
            "source_recommend_event_id": req.source_recommend_event_id,
            "recommend_session_id": req.recommend_session_id,
            "doc_id": req.doc_id,
            "user_id": req.user_id,
            "selected_text": req.selected_text,
            "context_prev": req.context_prev,
            "context_next": req.context_next,
            "target_category": category,
            "target_language": language,
            "target_intensity": intensity,
            "user_prompt": req.user_prompt,
            "selected_reco_option_index": req.selected_reco_option_index,
            "is_custom_option": req.is_custom_option,
            "created_at": _now_iso(),
            "paraphrase_llm_version": "cache-hit",
        }
        append_jsonl("b.jsonl", b_event)
        background_tasks.add_task(MongoLogger.log_event, "editor_run_paraphrasing", b_event)
        return ParaphraseResponse(candidates=cached_candidates)

    b_event = {
        "event": "editor_run_paraphrasing",
        "event_id": event_id,
        "source_recommend_event_id": req.source_recommend_event_id,
        "recommend_session_id": req.recommend_session_id,
        "doc_id": req.doc_id,
        "user_id": req.user_id,
        "selected_text": req.selected_text,
        "context_prev": req.context_prev,
        "context_next": req.context_next,
        "target_category": category,
        "target_language": language,
        "target_intensity": intensity,
        "user_prompt": req.user_prompt,
        "selected_reco_option_index": req.selected_reco_option_index,
        "is_custom_option": req.is_custom_option,
        "created_at": _now_iso(),
        "paraphrase_llm_version": "gpt-4.1-nano",
    }
    append_jsonl("b.jsonl", b_event)
    background_tasks.add_task(MongoLogger.log_event, "editor_run_paraphrasing", b_event)

    if _openai_client is None:
        print("OPENAI_API_KEY is not configured. Returning fallback candidates.")
        return ParaphraseResponse(candidates=fallback_candidates)

    try:
        prompt = build_paraphrase_prompt(
            selected_text=req.selected_text,
            category=category,
            intensity=intensity,
            language=language,
            user_prompt=req.user_prompt,
            context_prev=req.context_prev,
            context_next=req.context_next,
        )
        response = await _openai_client.chat.completions.create(
            model="gpt-4.1-nano",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt},
            ],
        )
        raw_text = (
            response.choices[0].message.content if response.choices else ""
        ) or ""
        candidates = _clean_candidates(raw_text, fallback_text)
        
        if candidates and candidates != fallback_candidates:
            await set_llm_cache(cache_key, candidates)
            
        return ParaphraseResponse(candidates=candidates)
    except Exception as exc:
        print(f"[OpenAI] Error during chat completion: {exc}")
        return ParaphraseResponse(candidates=fallback_candidates)


def trigger_immediate_profile_update(user_id: str):
    """
    Background Task로 실행될 함수:
    1. MongoDB 프로필 재계산 (Source of Truth 갱신)
    2. Qdrant 벡터 동기화 (Read Model 갱신)
    """
    try:
        print(f"[Trigger] Updating profile for {user_id} immediately...")
        from app.services.profile_service import ProfileService
        from app.services.sync_service import SyncService
        
        # [Fix] Initialize MongoClient locally to avoid NoneType error from global _mongo_client
        local_mongo_client = MongoClient(MONGO_URI)
        
        # 의존성 주입
        profile_service = ProfileService(mongo_client=local_mongo_client)
        
        # Qdrant Client는 매번 생성하거나 get_qdrant_client() 활용
        from app.qdrant.client import get_qdrant_client
        q_client = get_qdrant_client()
        sync_service = SyncService(mongo_client=local_mongo_client, qdrant_client=q_client)

        # 1. Mongo Update
        profile_service.update_user_profile(user_id)
        
        # 2. Qdrant Sync
        sync_service.sync_user_to_qdrant(user_id)
        
        print(f"[Trigger] Profile update & sync complete for {user_id}")
        
        # Close local connection
        local_mongo_client.close()
        
    except Exception as e:
        print(f"!!! CRITICAL PROFILE ERROR !!!")
        traceback.print_exc()
        print(f"[Trigger] Failed to update profile: {e}")


@app.post("/log")
def log_event(req: LogRequest, background_tasks: BackgroundTasks) -> Dict[str, Any]:
    payload: Dict[str, Any] = req.model_dump()
    
    # [DEBUG] Log the incoming payload to debug triggers
    print(f"🔥 [API_DEBUG] /log received payload: {payload}", flush=True)

    event = payload.get("event")
    
    # [DEBUG] Check event value
    print(f"🔍 [DEBUG] Event received: '{event}' (Type: {type(event)})", flush=True)

    # Standardize event names for logger
    if event == "editor_run_paraphrasing":
        append_jsonl("b.jsonl", payload)
        background_tasks.add_task(MongoLogger.log_event, "editor_run_paraphrasing", payload)
    elif event == "editor_selected_paraphrasing":
        print("🔥 [DEBUG] MATCHED: editor_selected_paraphrasing", flush=True)
        
        # 1. Log C (Original Event)
        append_jsonl("c.jsonl", payload)
        background_tasks.add_task(MongoLogger.log_event, "editor_selected_paraphrasing", payload)
        
        # 2. [Dual-Write] Log D (Correction History) generation
        input_text = payload.get("original_text")
        output_text = payload.get("selected_text") or payload.get("selected_candidate_text")

        if input_text and output_text:
            print(f"💾 [Dual-Write] Converting Log to Correction History (D)...", flush=True)
            
            d_doc = {
                "event": "correction_history",
                "insert_id": str(uuid.uuid4()),
                "user_id": payload.get("user_id"),
                "doc_id": payload.get("doc_id"),
                "recommend_session_id": payload.get("recommend_session_id"),
                
                # --- Mapping Logic ---
                "input_sentence": input_text,
                "output_sentences": [output_text], # List format
                "selected_index": 0,
                
                "intensity": payload.get("maintenance") or payload.get("intensity") or "moderate",
                "field": payload.get("field") or "general",
                
                "created_at": payload.get("created_at") or _now_iso(),
                "vector_synced": False
            }
            
            # Save D Log
            append_jsonl("d.jsonl", d_doc)
            background_tasks.add_task(MongoLogger.log_event, "correction_history", d_doc)
            print(f"✅ [Dual-Write] Created D-Log for user {d_doc['user_id']}", flush=True)

        # 3. Trigger Profile Update
        was_accepted = payload.get("was_accepted")
        print(f"🔥 [DEBUG] Checking was_accepted: {was_accepted} (Type: {type(was_accepted)})", flush=True)
        
        if was_accepted is True:
            user_id = payload.get("user_id")
            print(f"🚀 [Trigger] Immediate Profile Update for {user_id}", flush=True)
            if user_id:
                # [DEBUG] Run synchronously to debug logging issues
                trigger_immediate_profile_update(user_id)
        else:
            print("🔥 [DEBUG] was_accepted is not True", flush=True)

    elif event == "editor_document_snapshot":
        append_jsonl("k.jsonl", payload)
        background_tasks.add_task(MongoLogger.log_event, "editor_document_snapshot", payload)
    else:
        append_jsonl("others.jsonl", payload)
        background_tasks.add_task(MongoLogger.log_event, "others", payload)

    return {"status": "ok"}


app.include_router(auth_router, prefix="/auth")


@app.get("/documents")
def list_documents(user_id: str = Query(...)) -> Dict[str, Any]:
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="user_id is required",
        )

    collection = get_mongo_collection("full_document_store")
    cursor = collection.find({"user_id": user_id}).sort("last_synced_at", -1)

    items: list[Dict[str, Any]] = []
    for doc in cursor:
        doc_id = doc.get("doc_id")
        latest_full_text = doc.get("latest_full_text") or ""
        preview_text = latest_full_text[:50] if latest_full_text else "새 문서"
        last_synced_at = doc.get("last_synced_at")
        # 문자열로 정규화
        if isinstance(last_synced_at, (datetime,)):
            last_synced_at = last_synced_at.isoformat()
        items.append(
            {
                "doc_id": doc_id,
                "latest_full_text": latest_full_text,
                "preview_text": preview_text,
                "last_synced_at": last_synced_at,
            }
        )

    return {"items": items}


@app.delete("/documents/{doc_id}")
def delete_document(doc_id: str, user_id: str = Query(...)) -> Dict[str, Any]:
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="user_id is required",
        )

    collection = get_mongo_collection("full_document_store")
    result = collection.delete_one({"doc_id": doc_id, "user_id": user_id})
    return {"deleted": result.deleted_count}


@app.get("/documents/{doc_id}")
def get_document(doc_id: str, user_id: str = Query(...)) -> Dict[str, Any]:
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="user_id is required",
        )

    collection = get_mongo_collection("full_document_store")
    doc = collection.find_one({"doc_id": doc_id, "user_id": user_id})
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="document not found",
        )

    latest_full_text = doc.get("latest_full_text") or ""
    last_synced_at = doc.get("last_synced_at")
    if isinstance(last_synced_at, datetime):
        last_synced_at = last_synced_at.isoformat()

    return {
        "doc_id": doc_id,
        "user_id": user_id,
        "latest_full_text": latest_full_text,
        "last_synced_at": last_synced_at,
    }


@app.post("/documents")
def create_document(req: CreateDocumentRequest) -> Dict[str, Any]:
    if not req.user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="user_id is required",
        )

    collection = get_mongo_collection("full_document_store")
    doc_id = str(uuid.uuid4())
    now = _now_iso()

    doc = {
        "doc_id": doc_id,
        "user_id": req.user_id,
        "latest_full_text": "",
        "previous_full_text": None,
        "diff_ratio": 0.0,
        "created_at": now,
        "last_synced_at": now,
    }
    collection.insert_one(doc)

    return {"doc_id": doc_id, "created_at": now}


@app.patch("/documents/{doc_id}")
def update_document(
    doc_id: str, req: UpdateDocumentRequest, background_tasks: BackgroundTasks
) -> Dict[str, Any]:
    if not req.user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="user_id is required",
        )

    collection = get_mongo_collection("full_document_store")
    existing = collection.find_one({"doc_id": doc_id, "user_id": req.user_id})
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="document not found",
        )
    prev_text = existing.get("latest_full_text") or ""
    curr_text = req.latest_full_text or ""
    len_prev = len(prev_text)
    len_curr = len(curr_text)
    denominator = max(len_prev, 1)
    diff_ratio = abs(len_curr - len_prev) / denominator
    now = _now_iso()
    collection.update_one(
        {"_id": existing["_id"]},
        {
            "$set": {
                "latest_full_text": curr_text,
                "previous_full_text": prev_text,
                "diff_ratio": diff_ratio,
                "last_synced_at": now,
            }
        },
    )
    if diff_ratio >= 0.10 and curr_text:
        print(f"[Macro] Triggering Macro ETL for doc_id={doc_id} diff_ratio={diff_ratio:.3f}")
        background_tasks.add_task(analyze_and_cache_macro_context, doc_id, curr_text)
    return {"doc_id": doc_id, "status": "updated"}