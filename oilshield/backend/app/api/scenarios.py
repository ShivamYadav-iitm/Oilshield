"""Scenarios API router.

Exposes the Disruption Scenario Simulator endpoints, each a thin delegate to the
shared :class:`ScenarioSimulator` (see :mod:`app.api.deps`):

- ``GET /scenarios`` -- list the predefined scenarios with their full assumption
  sets, including each assumption's valid range and ``adjustable`` flag so the
  frontend can render bounded inputs (Requirements 5.1, 5.2).
- ``POST /scenarios/{id}/run`` -- start from a predefined scenario, apply any
  submitted in-range assumption overrides, and return the deterministic
  :class:`ImpactResult` together with the assumptions actually used (R5.3-5.5,
  R6.1, R6.2).
- ``POST /scenarios/save`` -- build a configured scenario from an id + optional
  overrides and persist it, returning the generated id (R7.1).
- ``GET /scenarios/saved/{id}`` -- restore a previously saved scenario, round-
  tripping its name and assumption values (R7.2, R7.3).

Validation and load failures raise ``ValidationError`` / ``ScenarioLoadError``,
which the app-wide handler (registered in :mod:`app.main`) serializes into the
standard JSON error envelope with the appropriate HTTP status (400).
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Depends

from app.api.deps import get_scenario_simulator
from app.models import Scenario
from app.services import ScenarioSimulator

router = APIRouter(prefix="/scenarios", tags=["scenarios"])


def _apply_overrides(
    simulator: ScenarioSimulator,
    scenario: Scenario,
    overrides: Optional[Dict[str, Any]],
) -> Scenario:
    """Apply a map of ``{assumption_key: value}`` overrides in order.

    Each override is routed through :meth:`ScenarioSimulator.apply_assumption`,
    so an unknown/non-adjustable key or an out-of-range value raises
    ``ValidationError`` (with its valid range) and the request fails cleanly
    without a partially-applied scenario (R5.3-5.5).
    """
    configured = scenario
    if overrides:
        for key, value in overrides.items():
            configured = simulator.apply_assumption(configured, key, value)
    return configured


def _extract_overrides(body: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Pull the assumption-override map out of a request body.

    Accepts either ``{"assumptions": {key: value, ...}}`` (preferred) or a bare
    ``{key: value, ...}`` map for convenience. Returns ``None`` when no overrides
    were supplied.
    """
    if not body:
        return None
    if "assumptions" in body and isinstance(body["assumptions"], dict):
        return body["assumptions"]
    # Bare map fallback; ignore known non-assumption keys.
    return {k: v for k, v in body.items() if k not in {"id", "scenario_id"}}


@router.get("")
def list_scenarios(
    simulator: ScenarioSimulator = Depends(get_scenario_simulator),
) -> Dict[str, Any]:
    """List the predefined scenarios with their assumptions (R5.1, R5.2).

    Returns:
        A JSON object with ``scenarios``: each predefined :class:`Scenario`
        serialized, including every :class:`ScenarioAssumption` with its value,
        valid range (``min_value``/``max_value``), ``adjustable`` flag, and unit.
    """
    scenarios = simulator.list_scenarios()
    return {
        "scenarios": [scenario.model_dump(mode="json") for scenario in scenarios],
    }


@router.post("/{scenario_id}/run")
def run_scenario(
    scenario_id: str,
    body: Optional[Dict[str, Any]] = Body(default=None),
    simulator: ScenarioSimulator = Depends(get_scenario_simulator),
) -> Dict[str, Any]:
    """Run a scenario, applying optional assumption overrides first.

    The optional JSON body may carry assumption overrides as
    ``{"assumptions": {key: value, ...}}``. Each override is validated and applied
    starting from the predefined scenario; an out-of-range value raises
    ``ValidationError`` -> error envelope (R5.3-5.5). The configured scenario is
    then run and its :class:`ImpactResult` returned (R6.1, R6.2).

    Returns:
        A JSON object with:
          - ``impact``: the serialized :class:`ImpactResult` (timeline + summary).
          - ``assumptions_used``: the assumption values applied to this run (R6.2).
    """
    scenario = simulator.get_scenario(scenario_id)
    overrides = _extract_overrides(body)
    configured = _apply_overrides(simulator, scenario, overrides)

    impact = simulator.run(configured)
    return {
        "impact": impact.model_dump(mode="json"),
        "assumptions_used": [
            assumption.model_dump(mode="json")
            for assumption in impact.assumptions_used
        ],
    }


@router.post("/save")
def save_scenario(
    body: Dict[str, Any] = Body(...),
    simulator: ScenarioSimulator = Depends(get_scenario_simulator),
) -> Dict[str, str]:
    """Build a configured scenario and persist it (R7.1).

    The body must identify a predefined scenario via ``id`` (or ``scenario_id``)
    and may carry assumption overrides via ``assumptions``. Overrides are
    validated and applied before saving; out-of-range values raise
    ``ValidationError`` -> error envelope.

    Returns:
        ``{"id": <saved-scenario-id>}`` -- the generated store id (R7.1).
    """
    scenario_id = body.get("id") or body.get("scenario_id")
    scenario = simulator.get_scenario(scenario_id)
    overrides = _extract_overrides(body)
    configured = _apply_overrides(simulator, scenario, overrides)

    saved_id = simulator.save(configured)
    return {"id": saved_id}


@router.get("/saved/{scenario_id}")
def load_saved_scenario(
    scenario_id: str,
    simulator: ScenarioSimulator = Depends(get_scenario_simulator),
) -> Dict[str, Any]:
    """Restore a previously saved scenario, round-tripping name + values (R7.2).

    A missing, malformed, or version-incompatible record raises
    ``ScenarioLoadError`` -> error envelope (R7.3).

    Returns:
        A JSON object with ``scenario``: the restored :class:`Scenario`
        serialized, whose name and assumption values equal those that were saved.
    """
    scenario = simulator.load(scenario_id)
    return {"scenario": scenario.model_dump(mode="json")}
