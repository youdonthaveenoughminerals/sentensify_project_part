# scripts/dashboard/test/test_dashboard_queries.py
"""
Pytest suite for dashboard v2.4 queries.
Verifies that query functions return correct data against a mock database.
"""
import pytest
import mongomock
import fakeredis
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock

# --- System path setup to allow importing dashboard modules ---
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../')))

# --- Module to be tested ---
from dashboard.queries import mongo as queries

# --- Constants ---
DB_NAME = "sentencify_test"
TEST_USER = "test_user"
OTHER_USER = "other_user"
PRICE_PER_RUN = 0.002 # As per prompt

# --- Fixtures for Mocking ---

@pytest.fixture(scope="function")
def mock_mongo_client():
    """Pytest fixture to provide a mongomock client and seed it with data."""
    client = mongomock.MongoClient()
    db = client[DB_NAME]
    
    # --- Seeding Scenario ---
    now = datetime.now(timezone.utc)
    
    # User A ("test_user")
    user_a_sessions = [f"session_a_{i}" for i in range(10)]
    db[queries.COLL_A].insert_many([{
        "recommend_session_id": sid, "user_id": TEST_USER, "created_at": now
    } for sid in user_a_sessions])
    
    db[queries.COLL_B].insert_many([{
        "recommend_session_id": sid, "user_id": TEST_USER, "created_at": now
    } for sid in user_a_sessions[:5]])

    db[queries.COLL_C].insert_many([{
        "recommend_session_id": sid, "user_id": TEST_USER, "was_accepted": True, "created_at": now
    } for sid in user_a_sessions[:3]])

    db[queries.COLL_H].insert_many([{
        "recommend_session_id": sid, "user_id": TEST_USER, "consistency_flag": "high"
    } for sid in user_a_sessions[:2]]) # 2 C's lead to high-quality H

    db[queries.COLL_K].insert_one({
        "doc_id": "doc_123", "user_id": TEST_USER, "diff_ratio": 0.15, "last_synced_at": now
    })

    # User B ("other_user")
    user_b_sessions = [f"session_b_{i}" for i in range(100)]
    db[queries.COLL_A].insert_many([{
        "recommend_session_id": sid, "user_id": OTHER_USER, "created_at": now
    } for sid in user_b_sessions])

    # --- Patch the query module's client getter ---
    with patch('dashboard.queries.mongo.get_mongo_client', return_value=client):
        with patch('dashboard.queries.mongo._mongo_db_name', return_value=DB_NAME):
            yield client

@pytest.fixture
def mock_redis_client():
    """Pytest fixture for a fake redis client."""
    r = fakeredis.FakeRedis()
    with patch('dashboard.queries.mongo.get_redis_client', return_value=r):
        yield r

# --- Test Cases ---

def test_system_health(mock_mongo_client, mock_redis_client):
    """Tests the health check functions."""
    # Test success case
    assert queries.check_mongo_health() is True
    assert queries.check_redis_health() is True

    # Test Mongo failure
    mock_db = mock_mongo_client[DB_NAME]
    mock_db.command = MagicMock(side_effect=Exception("Connection failed"))
    assert queries.check_mongo_health() is False

    # Test Redis failure
    mock_redis_client.ping = MagicMock(side_effect=Exception("Connection failed"))
    assert queries.check_redis_health() is False

def test_get_activity_window_map(mock_mongo_client):
    """Tests that activity map correctly reflects recent data."""
    # All data is fresh (<10s), so all components should be active
    activity = queries.get_activity_window_map(user_id=TEST_USER, seconds=60)
    assert activity["api"] is True
    assert activity["genai_run"] is True
    assert activity["worker"] is True

    # Check with an old timestamp
    old_activity = queries.get_activity_window_map(user_id="non_existent_user", seconds=1)
    assert old_activity["api"] is False
    assert old_activity["genai_run"] is False

def test_get_flow_counts_and_sankey_links(mock_mongo_client):
    """Tests the data flow counting for the Sankey/flow chart."""
    # Test with the specific test_user
    flow_counts = queries.get_flow_counts(user_id=TEST_USER)
    sankey_links = queries.get_sankey_links(user_id=TEST_USER)

    assert flow_counts["A"] == 10
    assert flow_counts["B"] == 5
    assert flow_counts["C_accepts"] == 3
    
    assert sankey_links["A_to_B"] == 5
    assert sankey_links["B_to_C"] == 3
    assert sankey_links["C_to_H"] == 2

    # Test with no filter (all users)
    total_flow_counts = queries.get_flow_counts()
    assert total_flow_counts["A"] == 110 # 10 for test_user + 100 for other_user

def test_get_cost_estimate(mock_mongo_client):
    """Tests the LLM cost estimation logic."""
    # Test for our specific test_user
    costs = queries.get_cost_estimate(user_id=TEST_USER)
    expected_cost = 5 * PRICE_PER_RUN
    assert abs(costs["cost"] - expected_cost) < 0.001
    assert costs["macro_queue"] == 1

    # Test total cost
    total_costs = queries.get_cost_estimate()
    assert abs(total_costs["cost"] - expected_cost) < 0.001 # other_user has no B logs

def test_user_filtering_is_applied(mock_mongo_client):
    """Explicitly verifies that user_id filtering works across multiple functions."""
    # get_total_counts
    user_a_counts = queries.get_total_counts(user_id=TEST_USER)
    assert user_a_counts["A"] == 10
    assert user_a_counts["B"] == 5
    assert user_a_counts["C"] == 3

    # get_recent_a_events
    recent_events = queries.get_recent_a_events(limit=20, user_id=TEST_USER)
    assert len(recent_events) == 10
    
    other_user_events = queries.get_recent_a_events(limit=20, user_id=OTHER_USER)
    assert len(other_user_events) == 20 # Capped by limit
    
    all_events = queries.get_recent_a_events(limit=120)
    assert len(all_events) == 110
