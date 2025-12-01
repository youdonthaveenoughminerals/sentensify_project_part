import pytest
from unittest.mock import MagicMock
from app.services.sync_service import SyncService

@pytest.fixture
def mock_mongo():
    client = MagicMock()
    # Mock db and collection
    db = MagicMock()
    client.__getitem__.return_value = db
    collection = MagicMock()
    db.__getitem__.return_value = collection
    return client

@pytest.fixture
def mock_qdrant():
    return MagicMock()

def test_sync_service_success(mock_mongo, mock_qdrant):
    service = SyncService(mock_mongo, mock_qdrant)
    
    # Mock user doc
    user_id = "test_user"
    mock_user_doc = {
        "user_id": user_id,
        "preferred_category_map": {"thesis": 0.8, "email": 0.2},
        "preferred_intensity_map": {"strong": 0.5, "moderate": 0.5},
        "user_embedding_v1": [0.1] * 768 # BERT dim
    }
    
    # Setup mocks
    service.users_col.find_one.return_value = mock_user_doc
    
    # Run
    result = service.sync_user_to_qdrant(user_id)
    
    # Assert
    assert result is True
    service.q_client.upsert.assert_called_once()
    # Check if payload has maps
    call_args = service.q_client.upsert.call_args
    points = call_args[1]['points']
    assert len(points) == 1
    assert points[0].payload['preferred_category_map']['thesis'] == 0.8

def test_sync_service_no_user(mock_mongo, mock_qdrant):
    service = SyncService(mock_mongo, mock_qdrant)
    service.users_col.find_one.return_value = None
    
    result = service.sync_user_to_qdrant("unknown")
    assert result is False
    mock_qdrant.upsert.assert_not_called()

def test_sync_service_no_embedding(mock_mongo, mock_qdrant):
    service = SyncService(mock_mongo, mock_qdrant)
    mock_user_doc = {
        "user_id": "no_emb",
        "preferred_category_map": {},
        "user_embedding_v1": [] # Empty
    }
    service.users_col.find_one.return_value = mock_user_doc
    
    result = service.sync_user_to_qdrant("no_emb")
    assert result is False # Should fail if no embedding for vector
    mock_qdrant.upsert.assert_not_called()
