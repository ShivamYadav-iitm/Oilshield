"""Tests for the procurement API router.

Covers the Adaptive Procurement Recommendations endpoint:

- ``POST /procurement/recommend`` returns a non-empty list of options ordered
  by ``recommendation_score`` descending (Requirement 8.4).
- Each returned option carries its full attribute set plus a non-empty
  rationale (R8.5).
- No returned option falls below the ``MIN_COMPAT`` grade-compatibility floor,
  confirming the exclusion step runs before ranking (R8.1, R8.3).
"""

from fastapi.testclient import TestClient

from app.core.constants import MIN_COMPAT
from app.main import app

client = TestClient(app)


def test_recommend_returns_non_empty_ranked_list():
    """POST /procurement/recommend returns options ranked high-to-low (R8.4)."""
    response = client.post("/procurement/recommend")
    assert response.status_code == 200

    body = response.json()
    recommendations = body["recommendations"]
    assert isinstance(recommendations, list)
    assert len(recommendations) > 0

    # Scores are non-increasing from first to last (R8.4).
    scores = [option["recommendation_score"] for option in recommendations]
    assert scores == sorted(scores, reverse=True)


def test_recommend_options_carry_attributes_and_rationale():
    """Each option exposes its full attribute set and a non-empty rationale (R8.5)."""
    response = client.post("/procurement/recommend")
    assert response.status_code == 200

    for option in response.json()["recommendations"]:
        assert "spot_price_usd_bbl" in option
        assert "tanker_availability" in option
        assert "port_congestion" in option
        assert "grade_compatibility" in option
        assert isinstance(option["rationale"], str)
        assert option["rationale"].strip() != ""


def test_recommend_excludes_options_below_min_compat():
    """No returned option is below the MIN_COMPAT floor (R8.1, R8.3)."""
    response = client.post("/procurement/recommend")
    assert response.status_code == 200

    for option in response.json()["recommendations"]:
        assert option["grade_compatibility"] >= MIN_COMPAT
