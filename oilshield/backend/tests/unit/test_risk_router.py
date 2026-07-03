"""Tests for the risk API router.

Covers the Live Risk Radar read endpoints:

- ``GET /risk/scores`` returns banded ``RiskScore``s for every known target,
  ranked highest-to-lowest (Requirements 3.5, 4.2).
- ``GET /risk/{target}/signals`` returns the contributing normalized signals for
  a selected corridor/country, each carrying its source and timestamp (R4.3),
  and echoes an empty list for an unknown target rather than erroring.
"""

from fastapi.testclient import TestClient

from app.api.deps import load_known_targets
from app.main import app

client = TestClient(app)


def test_scores_ranked_non_increasing_and_complete():
    """GET /risk/scores ranks every known target by score, highest first (R4.2)."""
    response = client.get("/risk/scores")
    assert response.status_code == 200

    body = response.json()
    assert "risk_scores" in body
    assert "data_source_modes" in body

    scores = body["risk_scores"]
    assert isinstance(scores, list)
    # One score per known target (corridor + supplier country), R3.1.
    assert len(scores) == len(load_known_targets())

    values = [entry["score"] for entry in scores]
    # Non-increasing order (R4.2).
    assert all(earlier >= later for earlier, later in zip(values, values[1:]))

    for entry in scores:
        assert 0.0 <= entry["score"] <= 100.0
        assert entry["band"] in {"low", "elevated", "high"}
        assert entry["target_type"] in {"corridor", "country"}


def test_target_signals_returns_contributing_signals_with_source_and_timestamp():
    """GET /risk/{target}/signals returns contributing signals with provenance (R4.3)."""
    response = client.get("/risk/Strait of Hormuz/signals")
    assert response.status_code == 200

    body = response.json()
    assert body["target"] == "Strait of Hormuz"
    signals = body["signals"]
    assert isinstance(signals, list)
    assert len(signals) > 0

    for signal in signals:
        assert signal["source"]  # non-empty source
        assert signal["timestamp"]  # carries a timestamp
        assert signal["target"].strip().lower() == "strait of hormuz"


def test_target_signals_case_insensitive_match():
    """The target path segment is matched case-insensitively (R4.3)."""
    response = client.get("/risk/strait of hormuz/signals")
    assert response.status_code == 200
    body = response.json()
    # Resolves to the canonical known-target name.
    assert body["target"] == "Strait of Hormuz"


def test_unknown_target_returns_empty_signals_without_error():
    """An unknown target echoes the requested name with an empty list, no 500 (R4.3)."""
    response = client.get("/risk/Atlantis/signals")
    assert response.status_code == 200
    body = response.json()
    assert body["target"] == "Atlantis"
    assert body["signals"] == []
