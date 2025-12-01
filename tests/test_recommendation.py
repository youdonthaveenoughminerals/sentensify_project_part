import pytest
from unittest.mock import MagicMock, Mock
from qdrant_client.http.models import ScoredPoint

# Import the function to be tested
from app.services.recommendation_service import recommend_intensity_by_similarity, DEFAULT_INTENSITY

@pytest.fixture
def mock_qdrant():
    return MagicMock()

@pytest.fixture
def mock_mongo():
    return MagicMock()

def create_scored_point(score, intensity=None, user_id=None):
    """Helper to create a ScoredPoint with a payload"""
    payload = {}
    # The service looks for 'preferred_intensity_map' (Dict) or 'current_intensity' (String - legacy/simple)
    # The implementation uses 'preferred_intensity_map' for weighted voting.
    # Let's simulate the map.
    if intensity:
        # Assuming the user has a strong preference for this intensity (1.0)
        payload["preferred_intensity_map"] = {intensity.lower(): 1.0}
    
    if user_id:
        payload["user_id"] = user_id
        
    return ScoredPoint(
        id=1, 
        version=1, 
        score=score, 
        payload=payload, 
        vector=None
    )

def test_recommendation_success_payload_only(mock_qdrant, mock_mongo):
    """
    Scenario 1: Qdrant Payload has all info (Intensity Map).
    User A (Score 0.9) prefers 'Strong'.
    User B (Score 0.8) prefers 'Strong'.
    User C (Score 0.95) prefers 'Weak'.
    """
    mock_hits = [
        create_scored_point(0.9, "Strong"),
        create_scored_point(0.8, "Strong"),
        create_scored_point(0.95, "Weak"),
    ]
    mock_qdrant.search.return_value = mock_hits

    # When
    result = recommend_intensity_by_similarity([0.1]*10, mock_qdrant, mock_mongo)

    # Then
    # Strong Score = (0.9 * 1.0) + (0.8 * 1.0) = 1.7
    # Weak Score = (0.95 * 1.0) = 0.95
    # Winner should be 'strong' (normalized)
    assert result == "strong"
    mock_mongo.find_one.assert_not_called()

def test_recommendation_fallback_mongo(mock_qdrant, mock_mongo):
    """
    Scenario 2: Qdrant Payload missing map, fallback to Mongo.
    """
    # Given: Qdrant returns user_id only
    mock_hits = [
        create_scored_point(0.9, user_id="user_1"),
    ]
    # Remove the map from payload to force fallback
    mock_hits[0].payload.pop("preferred_intensity_map", None)
    
    mock_qdrant.search.return_value = mock_hits

    # Mongo returns 'medium' preference for user_1
    mock_mongo.find_one.return_value = {
        "user_id": "user_1",
        "preferred_intensity_map": {"medium": 1.0}
    }

    # When
    result = recommend_intensity_by_similarity([0.1]*10, mock_qdrant, mock_mongo)

    # Then
    assert result == "medium"
    mock_mongo.find_one.assert_called_with({"user_id": "user_1"}, {"preferred_intensity_map": 1})

def test_cold_start_no_hits(mock_qdrant, mock_mongo):
    """
    Scenario 3: No similar users found.
    """
    mock_qdrant.search.return_value = []

    # When
    result = recommend_intensity_by_similarity([0.1]*10, mock_qdrant, mock_mongo)

    # Then
    assert result == DEFAULT_INTENSITY

def test_exception_handling(mock_qdrant, mock_mongo):
    """
    Scenario 4: Exception during search.
    """
    mock_qdrant.search.side_effect = Exception("Connection Error")

    # When
    result = recommend_intensity_by_similarity([0.1]*10, mock_qdrant, mock_mongo)

    # Then
    assert result == DEFAULT_INTENSITY

def test_empty_embedding_input(mock_qdrant, mock_mongo):
    """
    Scenario 5: Empty input embedding.
    """
    # When
    result = recommend_intensity_by_similarity([], mock_qdrant, mock_mongo)

    # Then
    assert result == DEFAULT_INTENSITY
    mock_qdrant.search.assert_not_called()
