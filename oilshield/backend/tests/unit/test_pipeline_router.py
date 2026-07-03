"""Tests for the pipeline API router.

Covers the end-to-end orchestration endpoint:

- ``POST /pipeline/run`` returns 200 with the staged :class:`PipelineResult`:
  non-empty ingested signals, ranked risk scores, and procurement
  recommendations (R9.1).
- The result reports a non-negative ``latency_ms`` (Pipeline_Latency, R9.2) and
  the per-source ``data_source_modes`` provenance (R9.1).
- ``linked_actions`` surfaces a Strait of Hormuz corridor entry (R9.3).
"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_run_returns_staged_pipeline_result():
    """POST /pipeline/run returns the full staged result (R9.1, R9.2)."""
    response = client.post("/pipeline/run")
    assert response.status_code == 200

    body = response.json()

    # Every stage produced output (R9.1).
    assert isinstance(body["signals"], list) and len(body["signals"]) > 0
    assert isinstance(body["risk_scores"], list) and len(body["risk_scores"]) > 0
    assert (
        isinstance(body["recommendations"], list)
        and len(body["recommendations"]) > 0
    )

    # Latency is measured and non-negative (R9.2).
    assert isinstance(body["latency_ms"], int)
    assert body["latency_ms"] >= 0

    # Provenance is present (R9.1).
    assert "data_source_modes" in body
    assert isinstance(body["data_source_modes"], dict)
    assert len(body["data_source_modes"]) > 0


def test_run_linked_actions_include_strait_of_hormuz():
    """linked_actions surfaces a Strait of Hormuz corridor entry (R9.3)."""
    response = client.post("/pipeline/run")
    assert response.status_code == 200

    linked_actions = response.json()["linked_actions"]
    assert isinstance(linked_actions, list)

    corridors = [action.get("corridor", "").lower() for action in linked_actions]
    assert any("strait of hormuz" in corridor for corridor in corridors)


def test_run_accepts_explicit_scenario_id():
    """POST /pipeline/run honors an explicit scenario_id in the body (R9.1)."""
    response = client.post(
        "/pipeline/run", json={"scenario_id": "hormuz_partial_closure"}
    )
    assert response.status_code == 200

    body = response.json()
    assert body["impact"] is not None
    assert body["latency_ms"] >= 0
