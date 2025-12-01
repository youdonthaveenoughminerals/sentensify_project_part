import os
import sys
import pytest
import fakeredis
import mongomock
from unittest.mock import patch

# Ensure dashboard is in python path so we can import 'queries'
dashboard_path = os.path.join(os.getcwd(), "dashboard")
if dashboard_path not in sys.path:
    sys.path.append(dashboard_path)

from queries.redis import get_cache_stats
from queries.mongo import get_macro_impact_stats, get_k_doc_count, get_recent_error_logs

@pytest.fixture
def mock_redis():
    r = fakeredis.FakeRedis(decode_responses=True)
    # Inject Phase 1.5 keys
    r.set("llm:para:test1", "micro_value_1")
    r.set("llm:para:test2", "micro_value_2")
    r.set("doc:123:macro", "macro_value_1")
    
    # Patch the get_redis_client in queries.redis namespace
    with patch("queries.redis.get_redis_client", return_value=r):
        yield r

@pytest.fixture
def mock_mongo():
    client = mongomock.MongoClient()
    db = client.sentencify
    # Inject A events with doc_maturity_score
    db.editor_recommend_options.insert_many([
        {"user_id": "u1", "doc_maturity_score": 0.1}, # Low
        {"user_id": "u1", "doc_maturity_score": 0.2}, # Low
        {"user_id": "u1", "doc_maturity_score": 0.5}, # Mid
        {"user_id": "u1", "doc_maturity_score": 0.8}, # High
    ])
    # Inject K docs
    db.full_document_store.insert_many([
        {"doc_id": "d1", "user_id": "u1"},
        {"doc_id": "d2", "user_id": "u1"},
        {"doc_id": "d3", "user_id": "u2"},
    ])
    # Inject High Latency Logs (COLL_I)
    db.recommend_log.insert_many([
        {"user_id": "u1", "latency_ms": 500},   # Normal
        {"user_id": "u1", "latency_ms": 2500},  # Anomaly
        {"user_id": "u1", "latency_ms": 3000},  # Anomaly
    ])
    
    # Patch the get_mongo_client in queries.mongo namespace
    with patch("queries.mongo.get_mongo_client", return_value=client):
        yield db

def test_get_cache_stats(mock_redis):
    patterns = ["llm:para:*", "doc:*:macro"]
    stats = get_cache_stats(patterns)
    
    # fakeredis should match 2 keys for llm:para:* and 1 for doc:*:macro
    assert stats["llm:para:*"] == 2
    assert stats["doc:*:macro"] == 1

def test_get_macro_impact_stats(mock_mongo):
    stats = get_macro_impact_stats(user_id="u1")
    
    # Avg: (0.1+0.2+0.5+0.8)/4 = 1.6/4 = 0.4
    assert stats["avg_alpha"] == pytest.approx(0.4)
    assert stats["buckets"]["low"] == 2
    assert stats["buckets"]["mid"] == 1
    assert stats["buckets"]["high"] == 1
    assert stats["count"] == 4

def test_get_k_doc_count(mock_mongo):
    # Total: 3 docs
    assert get_k_doc_count() == 3
    # User u1: 2 docs
    assert get_k_doc_count(user_id="u1") == 2
    # User u2: 1 doc
    assert get_k_doc_count(user_id="u2") == 1

def test_get_recent_error_logs(mock_mongo):
    # Should return 2 logs with latency > 2000ms
    errors = get_recent_error_logs(user_id="u1")
    assert len(errors) == 2
    latencies = [e["latency_ms"] for e in errors]
    assert 2500 in latencies
    assert 3000 in latencies
    assert 500 not in latencies
