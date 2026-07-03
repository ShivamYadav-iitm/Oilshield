"""Tests for the signals API router (POST /signals/refresh).

Verifies the happy-path refresh returns normalized signals plus the per-source
``Data_Source_Mode`` map (Requirements 1.1, 4.4).
"""

from fastapi.testclient import TestClient

from app.api.deps import get_ingestion_service
from app.main import app

client = TestClient(app)


def test_refresh_returns_signals_and_data_source_modes():
    """POST /signals/refresh returns normalized signals and a provenance map."""
    response = client.post("/signals/refresh")
    assert response.status_code == 200

    body = response.json()
    assert "signals" in body
    assert "data_source_modes" in body

    signals = body["signals"]
    assert isinstance(signals, list)
    assert len(signals) > 0

    # Every normalized signal carries the fully-populated fields (R1.2 shape).
    for signal in signals:
        assert signal["source"]
        assert signal["timestamp"]
        assert signal["text_summary"]
        assert signal["target"]
        assert signal["target_type"] in {"corridor", "country"}
        assert 0.0 <= signal["raw_severity"] <= 100.0
        assert signal["data_source_mode"] in {"live", "simulated"}


def test_refresh_reports_mode_for_every_configured_source():
    """The data_source_modes map has an entry per configured source (R1.6, R4.4)."""
    modes = client.post("/signals/refresh").json()["data_source_modes"]
    configured = get_ingestion_service().source_ids
    assert set(modes.keys()) == set(configured)
    assert all(mode in {"live", "simulated"} for mode in modes.values())
