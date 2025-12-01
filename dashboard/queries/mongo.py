from __future__ import annotations

import os
import socket
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import streamlit as st
from pymongo import MongoClient
import redis


# Collection names aligned with v2.4 schema (A~L)
COLL_A = "editor_recommend_options"
COLL_B = "editor_run_paraphrasing"
COLL_C = "editor_selected_paraphrasing"
COLL_D = "correction_history"
COLL_E = "context_block"
COLL_F = "document_context_cache"
COLL_G = "user_profile"
COLL_H = "training_examples"
COLL_I = "recommend_log"
COLL_K = "full_document_store"
COLL_L = "editor_document_snapshot"


def _mongo_uri() -> str:
    return os.getenv("MONGO_URI", "mongodb://localhost:27017")


def _mongo_db_name() -> str:
    return os.getenv("MONGO_DB_NAME", "sentencify")


@st.cache_resource
def get_mongo_client(uri: str | None = None) -> MongoClient:
    return MongoClient(uri or _mongo_uri())


@st.cache_resource
def get_redis_client() -> redis.Redis:
    host = os.getenv("REDIS_HOST", "localhost")
    port = int(os.getenv("REDIS_PORT", "6379"))
    return redis.Redis(host=host, port=port, decode_responses=True)


def _db():
    return get_mongo_client()[_mongo_db_name()]


def _col(name: str):
    return _db()[name]


def _with_user(filter_obj: Dict[str, Any], user_id: Optional[str]) -> Dict[str, Any]:
    if user_id:
        filter_obj = {**filter_obj, "user_id": user_id}
    return filter_obj


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


@st.cache_data(ttl=5)
def check_mongo_health() -> bool:
    try:
        _db().command("ping")
        return True
    except Exception:
        return False


@st.cache_data(ttl=5)
def check_redis_health() -> bool:
    try:
        get_redis_client().ping()
        return True
    except Exception:
        return False


@st.cache_data(ttl=5)
def check_vector_health() -> bool:
    """
    Lightweight TCP probe based on VECTOR_DB_HOST/PORT envs.
    Fallback: if TCP fails, treat as online when E docs exist in last minute (simulation).
    """
    host = os.getenv("VECTOR_DB_HOST")
    port = int(os.getenv("VECTOR_DB_PORT", "0") or "0")
    if host and port > 0:
        try:
            with socket.create_connection((host, port), timeout=1):
                return True
        except Exception:
            pass

    # Simulation fallback: recent E docs imply vector layer is "online"
    since = _now_utc() - timedelta(minutes=1)
    try:
        return _col(COLL_E).count_documents({"created_at": {"$gte": since}}) > 0
    except Exception:
        return False


def get_system_health() -> Dict[str, bool]:
    return {
        "mongo": check_mongo_health(),
        "redis": check_redis_health(),
        "vector": check_vector_health(),
    }


def _safe_count(coll: str, query: Dict[str, Any]) -> int:
    try:
        return _col(coll).count_documents(query)
    except Exception:
        return 0


@st.cache_data(ttl=5)
def get_total_counts(user_id: Optional[str] = None) -> Dict[str, int]:
    return {
        "A": _safe_count(COLL_A, _with_user({}, user_id)),
        "B": _safe_count(COLL_B, _with_user({}, user_id)),
        "C": _safe_count(COLL_C, _with_user({}, user_id)),
        "H": _safe_count(COLL_H, _with_user({}, user_id)),
        "E": _safe_count(COLL_E, _with_user({}, user_id)),
        "G": _safe_count(COLL_G, _with_user({}, user_id)),
    }


@st.cache_data(ttl=5)
def get_flow_counts(user_id: Optional[str] = None) -> Dict[str, int]:
    """
    Returns simple stage counts for Sankey: View (A) -> Run (B) -> Accept (C) -> Golden (H).
    """
    counts = get_total_counts(user_id)
    accepts = _safe_count(COLL_C, _with_user({"was_accepted": True}, user_id))
    counts["C_accepts"] = accepts
    return counts


@st.cache_data(ttl=5)
def get_sankey_links(user_id: Optional[str] = None) -> Dict[str, int]:
    """
    Approximates flow volumes:
    A->B: number of B events
    B->C: accepted C events
    C->H: high-consistency training examples
    """
    flows = {
        "A_to_B": _safe_count(COLL_B, _with_user({}, user_id)),
        "B_to_C": _safe_count(COLL_C, _with_user({"was_accepted": True}, user_id)),
        "C_to_H": _safe_count(COLL_H, _with_user({"consistency_flag": "high"}, user_id)),
    }
    return flows


@st.cache_data(ttl=5)
def get_asset_counts(user_id: Optional[str] = None) -> Dict[str, int]:
    return {
        "micro_contexts": _safe_count(COLL_E, _with_user({}, user_id)),
        "golden_data": _safe_count(COLL_H, _with_user({"consistency_flag": "high"}, user_id)),
    }


@st.cache_data(ttl=5)
def get_recent_a_events(limit: int = 5, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
    query = _with_user({}, user_id)
    try:
        cursor = (
            _col(COLL_A)
            .find(query, {"user_id": 1, "reco_category_input": 1, "created_at": 1, "latency_ms": 1})
            .sort("created_at", -1)
            .limit(limit)
        )
        return list(cursor)
    except Exception:
        return []


@st.cache_data(ttl=5)
def get_recent_runs(limit: int = 5, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
    query = _with_user({}, user_id)
    try:
        cursor = (
            _col(COLL_B)
            .find(query, {"user_id": 1, "target_category": 1, "target_language": 1, "created_at": 1})
            .sort("created_at", -1)
            .limit(limit)
        )
        return list(cursor)
    except Exception:
        return []


@st.cache_data(ttl=2)
def get_recent_activity_stream(limit: int = 20, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Aggregates recent A/B/C events to show a unified live stream.
    """
    query = _with_user({}, user_id)
    
    # 1. Fetch from A (Recommend)
    docs_a = list(_col(COLL_A).find(query, {
        "created_at": 1, "user_id": 1, "reco_category_input": 1, "latency_ms": 1
    }).sort("created_at", -1).limit(limit))
    
    # 2. Fetch from B (Run)
    docs_b = list(_col(COLL_B).find(query, {
        "created_at": 1, "user_id": 1, "target_category": 1, "target_intensity": 1
    }).sort("created_at", -1).limit(limit))

    # 3. Fetch from C (Select)
    docs_c = list(_col(COLL_C).find(query, {
        "created_at": 1, "user_id": 1, "was_accepted": 1, "selected_option_index": 1
    }).sort("created_at", -1).limit(limit))

    combined = []
    
    for d in docs_a:
        combined.append({
            "timestamp": d.get("created_at"),
            "event": "A (Recommend)",
            "user": d.get("user_id"),
            "detail": f"Cat: {d.get('reco_category_input')} | Latency: {d.get('latency_ms')}ms"
        })
        
    for d in docs_b:
        combined.append({
            "timestamp": d.get("created_at"),
            "event": "B (Run)",
            "user": d.get("user_id"),
            "detail": f"Target: {d.get('target_category')} ({d.get('target_intensity')})"
        })
        
    for d in docs_c:
        status = "Accepted" if d.get("was_accepted") else "Rejected"
        combined.append({
            "timestamp": d.get("created_at"),
            "event": "C (Select)",
            "user": d.get("user_id"),
            "detail": f"{status} (Idx: {d.get('selected_option_index')})"
        })

    # Sort by timestamp descending
    combined.sort(key=lambda x: x["timestamp"] if isinstance(x["timestamp"], datetime) else datetime.min, reverse=True)
    
    return combined[:limit]


@st.cache_data(ttl=5)
def get_latency_series(limit: int = 50, user_id: Optional[str] = None) -> List[Tuple[datetime, float]]:
    query = _with_user({}, user_id)
    try:
        cursor = (
            _col(COLL_I)
            .find(query, {"latency_ms": 1, "created_at": 1})
            .sort("created_at", -1)
            .limit(limit)
        )
        series = [(doc.get("created_at"), float(doc.get("latency_ms", 0))) for doc in cursor if doc.get("latency_ms") is not None]
        series.reverse()
        return series
    except Exception:
        return []


@st.cache_data(ttl=5)
def get_latency_summary(user_id: Optional[str] = None) -> Dict[str, float]:
    series = get_latency_series(limit=200, user_id=user_id)
    if not series:
        return {"avg": 0.0, "p95": 0.0}
    values = [lat for _, lat in series]
    values_sorted = sorted(values)
    p95_index = int(len(values_sorted) * 0.95) - 1
    p95_index = max(0, min(p95_index, len(values_sorted) - 1))
    return {
        "avg": sum(values) / len(values),
        "p95": values_sorted[p95_index],
    }


@st.cache_data(ttl=5)
def get_cache_hit_rate() -> float:
    try:
        stats = get_redis_client().info("stats")
        hits = stats.get("keyspace_hits", 0)
        misses = stats.get("keyspace_misses", 0)
        total = hits + misses
        return (hits / total) if total else 0.0
    except Exception:
        return 0.0


@st.cache_data(ttl=5)
def get_macro_queue_length() -> int:
    """Documents requiring macro refresh (diff_ratio >= 0.1)."""
    return _safe_count(COLL_K, {"diff_ratio": {"$gte": 0.1}})


@st.cache_data(ttl=5)
def get_macro_cache_samples(limit: int = 3) -> List[Dict[str, Any]]:
    try:
        cursor = (
            _col(COLL_F)
            .find({}, {"doc_id": 1, "macro_topic": 1, "macro_category_hint": 1, "last_updated": 1})
            .sort("last_updated", -1)
            .limit(limit)
        )
        return list(cursor)
    except Exception:
        return []


@st.cache_data(ttl=5)
def get_component_cost(per_call_cost: float = 0.002, user_id: Optional[str] = None) -> float:
    runs = _safe_count(COLL_B, _with_user({}, user_id))
    return round(runs * per_call_cost, 4)


def get_cost_estimate(user_id: Optional[str] = None) -> Dict[str, float]:
    cost = get_component_cost(user_id=user_id)
    queue = get_macro_queue_length()
    return {"cost": cost, "macro_queue": queue}


@st.cache_data(ttl=5)
def get_node_recency_map(user_id: Optional[str] = None, lookback_seconds: int = 60) -> Dict[str, float]:
    """
    Returns seconds since last event per component (api, worker, mongo, redis, vectordb, emb_model, genai_run, genai_macro).
    If no event in lookback window, returns 999.0.
    """
    now = _now_utc()
    since = now - timedelta(seconds=lookback_seconds)

    def age_seconds(coll: str, ts_field: str = "created_at") -> float:
        query = _with_user({ts_field: {"$gte": since}}, user_id)
        try:
            doc = _col(coll).find_one(query, sort=[(ts_field, -1)], projection={ts_field: 1})
            if not doc or not doc.get(ts_field):
                return 999.0
            delta = now - doc[ts_field]
            return max(delta.total_seconds(), 0.0)
        except Exception:
            return 999.0

    return {
        "api": age_seconds(COLL_A),
        "worker": age_seconds(COLL_K, "last_synced_at"),
        "mongo": age_seconds(COLL_A),
        "redis": age_seconds(COLL_F, "last_updated"),
        "vectordb": age_seconds(COLL_E),
        "emb_model": age_seconds(COLL_I),
        "genai_run": age_seconds(COLL_B),
        "genai_macro": age_seconds(COLL_F, "last_updated"),
    }

@st.cache_data(ttl=10)
def get_macro_impact_stats(user_id: Optional[str] = None) -> Dict[str, Any]:
    match_stage = _with_user({}, user_id)
    match_stage["doc_maturity_score"] = {"$exists": True, "$ne": None}
    
    pipeline = [
        {"$match": match_stage},
        {"$group": {
            "_id": None,
            "avg_alpha": {"$avg": "$doc_maturity_score"},
            "bucket_low": {"$sum": {"$cond": [{"$lt": ["$doc_maturity_score", 0.3]}, 1, 0]}},
            "bucket_mid": {"$sum": {"$cond": [{"$and": [{"$gte": ["$doc_maturity_score", 0.3]}, {"$lt": ["$doc_maturity_score", 0.7]}]}, 1, 0]}},
            "bucket_high": {"$sum": {"$cond": [{"$gte": ["$doc_maturity_score", 0.7]}, 1, 0]}},
            "count": {"$sum": 1}
        }}
    ]
    
    try:
        res = list(_col(COLL_A).aggregate(pipeline))
        if not res:
            return {"avg_alpha": 0.0, "buckets": {"low": 0, "mid": 0, "high": 0}, "count": 0}
        
        data = res[0]
        return {
            "avg_alpha": data.get("avg_alpha", 0.0),
            "buckets": {
                "low": data.get("bucket_low", 0),
                "mid": data.get("bucket_mid", 0),
                "high": data.get("bucket_high", 0)
            },
            "count": data.get("count", 0)
        }
    except Exception:
        return {"avg_alpha": 0.0, "buckets": {"low": 0, "mid": 0, "high": 0}, "count": 0}

@st.cache_data(ttl=10)
def get_hybrid_score_ratio(user_id: Optional[str] = None) -> Dict[str, float]:
    match_stage = _with_user({}, user_id)
    match_stage["applied_weight_doc"] = {"$exists": True, "$ne": None}
    
    pipeline = [
        {"$match": match_stage},
        {"$group": {
            "_id": None,
            "avg_alpha": {"$avg": "$applied_weight_doc"}
        }}
    ]
    
    try:
        res = list(_col(COLL_A).aggregate(pipeline))
        if not res:
            return {"macro_ratio": 0.0, "micro_ratio": 1.0}
        
        avg_alpha = res[0].get("avg_alpha", 0.0)
        return {"macro_ratio": avg_alpha, "micro_ratio": 1.0 - avg_alpha}
    except Exception:
        return {"macro_ratio": 0.0, "micro_ratio": 1.0}

@st.cache_data(ttl=5)
def get_k_doc_count(user_id: Optional[str] = None) -> int:
    """Returns the total count of full documents."""
    return _safe_count(COLL_K, _with_user({}, user_id))

@st.cache_data(ttl=5)
def get_recent_error_logs(limit: int = 5, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Fetches critical error logs.
    Since we don't have a dedicated error log collection yet, we use log_i_recommend (COLL_I)
    and filter for high latency (> 2000ms) as a proxy for 'anomaly' or potential error.
    """
    query = _with_user({"latency_ms": {"$gt": 2000}}, user_id)
    try:
        cursor = (
            _col(COLL_I)
            .find(query, {"user_id": 1, "doc_id": 1, "latency_ms": 1, "created_at": 1})
            .sort("created_at", -1)
            .limit(limit)
        )
        return list(cursor)
    except Exception:
        return []


@st.cache_data(ttl=5)
def get_recent_docs(collection_name: str, limit: int = 10, user_id: Optional[str] = None, fields: Optional[Dict] = None) -> List[Dict[str, Any]]:
    """
    Generic fetcher for recent documents from a collection.
    """
    query = _with_user({}, user_id)
    try:
        # Default sort by created_at if it exists, otherwise natural order
        sort_field = "created_at"
        
        # Special handling for collections that might use different timestamp fields
        if collection_name == COLL_F:
            sort_field = "last_updated"
        elif collection_name == COLL_K:
            sort_field = "last_synced_at"

        cursor = (
            _col(collection_name)
            .find(query, fields)
            .sort(sort_field, -1)
            .limit(limit)
        )
        return list(cursor)
    except Exception:
        return []


@st.cache_data(ttl=5)
def get_recent_upserts(limit: int = 10, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Fetches recent Vector DB upserts (context blocks).
    """
    return get_recent_docs(COLL_E, limit, user_id, {"doc_id": 1, "field": 1, "preview_text": 1, "created_at": 1})


# --- Phase 1 Performance Analytics ---

@st.cache_data(ttl=10)
def get_conversion_funnel(user_id: Optional[str] = None) -> Dict[str, int]:
    """
    Calculates unique session counts for View (A) -> Run (B) -> Accept (C).
    """
    match_stage = _with_user({}, user_id)
    
    # View Count: Unique sessions in A
    view_count = len(_col(COLL_A).distinct("recommend_session_id", match_stage))
    
    # Run Count: Unique sessions in B (that also exist in A ideally, but simplified here)
    run_count = len(_col(COLL_B).distinct("recommend_session_id", match_stage))
    
    # Accept Count: Unique sessions in C where was_accepted=True
    accept_match = {**match_stage, "was_accepted": True}
    accept_count = len(_col(COLL_C).distinct("recommend_session_id", accept_match))
    
    return {
        "view": view_count,
        "run": run_count,
        "accept": accept_count
    }

@st.cache_data(ttl=10)
def get_rule_vs_vector_stats(user_id: Optional[str] = None, limit: int = 1000) -> Dict[str, Any]:
    """
    Analyzes Rule Engine intervention rate and P_vec correlation.
    Returns:
      - rule_trigger_rate: Ratio of logs where P_rule is present/non-empty.
      - scatter_data: List of points {x: P_vec, y: P_rule} for plotting.
    """
    match_stage = _with_user({}, user_id)
    
    # We need logs that have P_vec. P_rule is optional or might be empty.
    # Projection to minimize data transfer
    projection = {"P_vec": 1, "P_rule": 1, "_id": 0}
    
    cursor = _col(COLL_A).find(match_stage, projection).sort("created_at", -1).limit(limit)
    
    points = []
    rule_triggered_count = 0
    total_count = 0
    
    for doc in cursor:
        total_count += 1
        
        # Extract max score from P_vec (assuming dict {category: score})
        p_vec_scores = doc.get("P_vec", {}) or {}
        max_p_vec = max(p_vec_scores.values()) if p_vec_scores else 0.0
        
        # Extract max score from P_rule
        p_rule_scores = doc.get("P_rule", {}) or {}
        max_p_rule = max(p_rule_scores.values()) if p_rule_scores else 0.0
        
        if max_p_rule > 0:
            rule_triggered_count += 1
            
        points.append({"x": max_p_vec, "y": max_p_rule})
        
    trigger_rate = (rule_triggered_count / total_count) if total_count > 0 else 0.0
    
    return {
        "rule_trigger_rate": trigger_rate,
        "scatter_data": points
    }

@st.cache_data(ttl=10)
def get_latency_breakdown(user_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Calculates P50, P95, P99 latency and basic time-series data.
    """
    match_stage = _with_user({}, user_id)
    match_stage["latency_ms"] = {"$exists": True, "$ne": None}
    
    # Sort by time for trend, then extract values
    cursor = _col(COLL_I).find(match_stage, {"latency_ms": 1, "created_at": 1}).sort("created_at", -1).limit(500)
    data = list(cursor)
    
    if not data:
        return {"p50": 0, "p95": 0, "p99": 0, "trend": []}
    
    latencies = sorted([d["latency_ms"] for d in data])
    n = len(latencies)
    
    def get_percentile(p):
        idx = int(n * p)
        return latencies[min(idx, n - 1)]
    
    # Trend data (simple list of dicts)
    trend = [{"timestamp": d["created_at"], "latency": d["latency_ms"]} for d in data]
    
    return {
        "p50": get_percentile(0.50),
        "p95": get_percentile(0.95),
        "p99": get_percentile(0.99),
        "trend": trend
    }

@st.cache_data(ttl=10)
def get_user_intent_stats(user_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Aggregates distribution of Categories (field) and Intensity.
    Uses COLL_A as a proxy for user intent (input context).
    Note: COLL_A doesn't strictly store 'field' as user selection, but 'reco_category_input' is the recommendation.
    Better to use COLL_B (Run) or COLL_D (History) for explicit user choice.
    Let's use COLL_B for 'Active Intent'.
    """
    match_stage = _with_user({}, user_id)
    
    # Aggregate Category
    cat_pipeline = [
        {"$match": match_stage},
        {"$group": {"_id": "$target_category", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}
    ]
    
    # Aggregate Intensity
    int_pipeline = [
        {"$match": match_stage},
        {"$group": {"_id": "$target_intensity", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}
    ]
    
    cats = list(_col(COLL_B).aggregate(cat_pipeline))
    ints = list(_col(COLL_B).aggregate(int_pipeline))
    
    return {
        "categories": {d["_id"]: d["count"] for d in cats if d["_id"]},
        "intensities": {d["_id"]: d["count"] for d in ints if d["_id"]}
    }


def get_collection_names() -> List[str]:
    """Returns a list of all collection names in the database."""
    try:
        return sorted(_db().list_collection_names())
    except Exception:
        return []


def find_documents(collection_name: str, filter_query: Dict[str, Any], limit: int = 50) -> List[Dict[str, Any]]:
    """
    Fetches documents from a collection with optional filtering.
    Sorts by created_at descending if available, otherwise natural order.
    """
    try:
        # Check if created_at exists to sort by it
        # sort_key = [("$natural", -1)]
        
        # Simple heuristic: most of our collections use 'created_at'
        # We can try to sort by it, but if it doesn't exist, Mongo doesn't error on sort, just ignores or puts them at end.
        # Safer to use _id desc which implies time for ObjectId
        sort_key = [("_id", -1)]

        cursor = _col(collection_name).find(filter_query).sort(sort_key).limit(limit)
        
        # Convert ObjectId and datetime to string for easier display
        docs = []
        for doc in cursor:
            # Shallow copy to modify
            d = doc.copy()
            if "_id" in d:
                d["_id"] = str(d["_id"])
            # Convert common datetime fields
            for k, v in d.items():
                if isinstance(v, datetime):
                    d[k] = v.isoformat()
            docs.append(d)
            
        return docs
    except Exception:
        return []
    