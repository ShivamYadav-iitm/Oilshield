"""Pipeline API router.

Exposes the end-to-end orchestration endpoint, a thin delegate to the shared
:class:`PipelineOrchestrator` (see :mod:`app.api.deps`):

- ``POST /pipeline/run`` -- run the whole "signal to recommendation" flow in one
  request and return the staged :class:`~app.models.PipelineResult`: ingested
  signals, ranked risk scores, scenario impact, procurement recommendations, the
  cross-module ``linked_actions``, the measured ``latency_ms`` (Pipeline_Latency,
  R9.2), and the per-source ``data_source_modes`` provenance (R9.1). An optional
  JSON body ``{"scenario_id": <id>}`` selects the scenario to simulate; when
  omitted the orchestrator auto-selects one from the highest "high"-band corridor.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Depends

from app.api.deps import get_pipeline_orchestrator
from app.services import PipelineOrchestrator

router = APIRouter(prefix="/pipeline", tags=["pipeline"])


@router.post("/run")
def run_pipeline(
    body: Optional[Dict[str, Any]] = Body(default=None),
    orchestrator: PipelineOrchestrator = Depends(get_pipeline_orchestrator),
) -> Dict[str, Any]:
    """Run the full pipeline and return the staged result (R9.1, R9.2).

    Delegates to :meth:`PipelineOrchestrator.run`, which sequences ingestion,
    extraction, risk scoring, scenario impact, and procurement, times the run,
    and derives the ``linked_actions`` for any "high"-band corridor.

    Args:
        body: Optional JSON object; when it contains ``scenario_id`` that
            scenario is simulated, otherwise the orchestrator auto-selects one.

    Returns:
        The serialized :class:`~app.models.PipelineResult` with every stage
        output plus ``latency_ms`` and ``data_source_modes``.
    """
    scenario_id: Optional[str] = None
    if body is not None:
        scenario_id = body.get("scenario_id")

    result = orchestrator.run(scenario_id)
    return result.model_dump(mode="json")
