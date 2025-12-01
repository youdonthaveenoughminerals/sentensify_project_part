import os
import sys
import pytest
import mongomock
from unittest.mock import patch

# Ensure dashboard is in python path
dashboard_path = os.path.join(os.getcwd(), "dashboard")
if dashboard_path not in sys.path:
    sys.path.append(dashboard_path)

from queries.mongo import get_conversion_funnel

@pytest.fixture
def mock_mongo_phase1():
    client = mongomock.MongoClient()
    db = client.sentencify
    
    # Scenario:
    # Session 1: View -> Run -> Accept (Success Chain)
    # Session 2: View -> Run (Drop off)
    # Session 3: View (Bounce)
    # Session 4: View -> Run -> Accept (Success Chain)
    
    # A (View): 4 sessions
    db.editor_recommend_options.insert_many([
        {"recommend_session_id": "s1", "user_id": "u1"},
        {"recommend_session_id": "s2", "user_id": "u1"},
        {"recommend_session_id": "s3", "user_id": "u2"},
        {"recommend_session_id": "s4", "user_id": "u2"},
    ])
    
    # B (Run): 3 sessions (s1, s2, s4)
    db.editor_run_paraphrasing.insert_many([
        {"recommend_session_id": "s1", "user_id": "u1"},
        {"recommend_session_id": "s2", "user_id": "u1"},
        {"recommend_session_id": "s4", "user_id": "u2"},
    ])
    
    # C (Accept): 2 sessions (s1, s4) - s2 didn't accept (or was_accepted=False)
    db.editor_selected_paraphrasing.insert_many([
        {"recommend_session_id": "s1", "user_id": "u1", "was_accepted": True},
        {"recommend_session_id": "s2", "user_id": "u1", "was_accepted": False}, # Explicit reject
        {"recommend_session_id": "s4", "user_id": "u2", "was_accepted": True},
    ])
    
    with patch("queries.mongo.get_mongo_client", return_value=client):
        yield db

def test_get_conversion_funnel(mock_mongo_phase1):
    # Test Global Funnel
    funnel = get_conversion_funnel()
    assert funnel["view"] == 4
    assert funnel["run"] == 3
    assert funnel["accept"] == 2  # Only true accepts
    
    # Test User Filter (u1) -> s1(acc), s2(rej)
    funnel_u1 = get_conversion_funnel(user_id="u1")
    assert funnel_u1["view"] == 2
    assert funnel_u1["run"] == 2
    assert funnel_u1["accept"] == 1
