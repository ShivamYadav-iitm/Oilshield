"""Tests for the scenarios API router.

Covers the Disruption Scenario Simulator endpoints:

- ``GET /scenarios`` lists the three predefined scenarios, each with its
  assumptions and valid ranges (Requirements 5.1, 5.2).
- ``POST /scenarios/{id}/run`` runs a scenario and returns a per-day timeline
  plus the assumptions used (R6.1, R6.2).
- An out-of-range assumption override is rejected via the standard error
  envelope with a 400 status (R5.5).
- ``POST /scenarios/save`` then ``GET /scenarios/saved/{id}`` round-trips the
  scenario's name and assumption values (R7.1, R7.2).
"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_list_scenarios_returns_three_with_assumptions():
    """GET /scenarios lists the 3 predefined scenarios with assumptions (R5.1, R5.2)."""
    response = client.get("/scenarios")
    assert response.status_code == 200

    body = response.json()
    scenarios = body["scenarios"]
    assert isinstance(scenarios, list)
    assert len(scenarios) == 3

    for scenario in scenarios:
        assert scenario["id"]
        assert scenario["name"]
        assumptions = scenario["assumptions"]
        assert isinstance(assumptions, list)
        assert len(assumptions) > 0
        for assumption in assumptions:
            # Each assumption exposes its value, valid range, and adjustable flag
            # so the frontend can render bounded inputs (R5.2, R5.3).
            assert "value" in assumption
            assert "min_value" in assumption
            assert "max_value" in assumption
            assert "adjustable" in assumption


def test_run_hormuz_closure_returns_timeline():
    """POST /scenarios/{id}/run returns a per-day impact timeline (R6.1, R6.6)."""
    response = client.post(
        "/scenarios/hormuz_partial_closure/run",
        json={"assumptions": {"corridor_closure_pct": 80.0, "duration_days": 30}},
    )
    assert response.status_code == 200

    body = response.json()
    impact = body["impact"]
    assert impact["scenario_id"] == "hormuz_partial_closure"

    timeline = impact["timeline"]
    # Exactly one point per day of duration_days (R6.6).
    assert len(timeline) == 30
    for point in timeline:
        assert "refinery_run_rate_pct" in point
        assert "fuel_price_index" in point
        assert point["spr_days_of_cover"] >= 0.0  # SPR floor (R6.4)
        assert "gdp_index" in point

    # Assumptions used are reported alongside results (R6.2).
    used = {a["key"]: a["value"] for a in body["assumptions_used"]}
    assert used["corridor_closure_pct"] == 80.0
    assert used["duration_days"] == 30.0


def test_out_of_range_override_returns_error_envelope():
    """An out-of-range override yields the JSON error envelope with a 400 (R5.5)."""
    response = client.post(
        "/scenarios/hormuz_partial_closure/run",
        json={"assumptions": {"corridor_closure_pct": 250.0}},
    )
    assert response.status_code == 400

    body = response.json()
    assert "error" in body
    error = body["error"]
    assert error["module"] == "scenario_simulator"
    assert error["code"] == "VALIDATION_ERROR"
    # The message communicates the valid range back to the client (R5.5).
    assert "range" in error["message"].lower()


def test_save_then_load_round_trips_name_and_assumptions():
    """POST /scenarios/save then GET /scenarios/saved/{id} round-trips (R7.1, R7.2)."""
    save_response = client.post(
        "/scenarios/save",
        json={
            "id": "hormuz_partial_closure",
            "assumptions": {"corridor_closure_pct": 75.0, "duration_days": 20},
        },
    )
    assert save_response.status_code == 200
    saved_id = save_response.json()["id"]
    assert saved_id

    load_response = client.get(f"/scenarios/saved/{saved_id}")
    assert load_response.status_code == 200

    scenario = load_response.json()["scenario"]
    assert scenario["name"] == "Strait of Hormuz partial closure"

    values = {a["key"]: a["value"] for a in scenario["assumptions"]}
    assert values["corridor_closure_pct"] == 75.0
    assert values["duration_days"] == 20.0


def test_load_unknown_saved_scenario_returns_error_envelope():
    """Loading a missing saved scenario raises ScenarioLoadError -> envelope (R7.3)."""
    response = client.get("/scenarios/saved/does-not-exist-id")
    assert response.status_code == 400

    body = response.json()
    assert body["error"]["code"] == "SCENARIO_LOAD_ERROR"
