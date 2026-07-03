"""Pipeline Orchestrator service.

The ``PipelineOrchestrator`` runs the whole OilShield "signal to recommendation"
flow end-to-end in a fixed sequence -- ingestion -> extraction -> risk scoring ->
scenario impact -> procurement -- and bundles every stage output into a single
:class:`~app.models.PipelineResult` (R9.1). It also measures the wall-clock
``Pipeline_Latency`` for the whole run (R9.2), surfaces linked scenario /
procurement actions for any corridor that enters the "high" band (R9.3), and
isolates stage failures so a broken stage never wipes out the results of the
stages that already completed (R10.5).

Behavior:

- **Sequenced stages (R9.1):** ingestion feeds extraction, extraction feeds
  scoring; scenario impact and procurement then run to complete the picture.
- **Latency (R9.2):** the total run time is measured with a monotonic clock and
  reported as a non-negative ``latency_ms``.
- **Linked actions (R9.3):** for every corridor whose ``RiskScore`` lands in the
  "high" band, an action dict is added to ``linked_actions`` referencing that
  corridor plus a recommended scenario id and the top procurement option id.
- **Stage isolation (R10.5):** each stage is wrapped so a failure is recorded
  against that stage (logged) while the outputs of already-completed stages are
  preserved. The returned :class:`PipelineResult` carries whatever completed
  (``impact`` may be ``None`` if the scenario stage failed).

Determinism / latency: every stage delegates to the deterministic-by-default
service layer (simulated data source, deterministic extractor, pure scoring /
impact / recommendation math), so a full simulated run completes well within the
15-second budget (R9.4).

Requirements: 9.1, 9.2, 9.3, 10.5
"""

from __future__ import annotations

import logging
import time
from typing import Dict, List, Optional

from app.models import (
    ExtractedSignal,
    ImpactResult,
    PipelineResult,
    ProcurementOption,
    RiskScore,
    Signal,
)
from app.services.extractor import LLMExtractor
from app.services.ingestion import SignalIngestionService
from app.services.recommender import ProcurementRecommender
from app.services.scoring import RiskScoringEngine
from app.services.simulator import ScenarioSimulator

__all__ = ["PipelineOrchestrator"]

logger = logging.getLogger(__name__)

# Fallback scenario used when no "high"-band corridor is present or a corridor
# has no dedicated scenario (R9.3, auto-selection).
_DEFAULT_SCENARIO_ID = "hormuz_partial_closure"

# Map a corridor's canonical name (case-insensitive) to the predefined scenario
# that best models its disruption. Kept in sync with the simulator catalog.
_CORRIDOR_SCENARIO: Dict[str, str] = {
    "strait of hormuz": "hormuz_partial_closure",
    "red sea": "red_sea_shutdown",
}


class PipelineOrchestrator:
    """Run the full OilShield pipeline and assemble a :class:`PipelineResult`.

    The orchestrator owns no business logic of its own: it sequences the service
    layer, times the run, isolates stage failures, and derives the cross-module
    ``linked_actions`` for high-band corridors.
    """

    def __init__(
        self,
        ingestion: SignalIngestionService,
        extractor: LLMExtractor,
        scoring: RiskScoringEngine,
        simulator: ScenarioSimulator,
        recommender: ProcurementRecommender,
    ) -> None:
        """Create the orchestrator over the five pipeline services.

        Args:
            ingestion: Stage 1 -- normalized signal ingestion.
            extractor: Stage 2 -- structured signal extraction.
            scoring: Stage 3 -- risk scoring / banding / ranking.
            simulator: Stage 4 -- scenario impact cascade.
            recommender: Stage 5 -- procurement recommendations.
        """
        self._ingestion = ingestion
        self._extractor = extractor
        self._scoring = scoring
        self._simulator = simulator
        self._recommender = recommender

    def run(self, scenario_id: Optional[str] = None) -> PipelineResult:
        """Run the end-to-end pipeline and return a staged :class:`PipelineResult`.

        Stages run in sequence (R9.1). Each stage is isolated so a failure is
        recorded against that stage while the outputs of completed stages are
        preserved (R10.5); the returned result carries whatever completed.
        ``latency_ms`` measures the whole run with a monotonic clock (R9.2), and
        ``linked_actions`` surfaces high-band corridors (R9.3).

        Args:
            scenario_id: An explicit scenario to simulate. When omitted, a
                scenario is auto-selected from the highest "high"-band corridor
                (falling back to the Hormuz partial-closure scenario).

        Returns:
            A :class:`PipelineResult` with the staged outputs, provenance,
            linked actions, and measured latency.
        """
        start = time.monotonic()

        signals: List[Signal] = []
        extracted: List[ExtractedSignal] = []
        risk_scores: List[RiskScore] = []
        impact: Optional[ImpactResult] = None
        recommendations: List[ProcurementOption] = []
        data_source_modes: Dict[str, str] = {}
        # Per-stage status so a failure is recorded against its stage while the
        # completed stages are preserved (R10.5).
        stage_status: Dict[str, str] = {}

        # -- Stage 1: ingestion ----------------------------------------------
        try:
            ingestion_result = self._ingestion.refresh()
            signals = list(ingestion_result.signals)
            data_source_modes = {
                source_id: str(mode)
                for source_id, mode in ingestion_result.data_source_modes.items()
            }
            stage_status["ingestion"] = "ok"
        except Exception as exc:  # noqa: BLE001 - isolate the stage (R10.5)
            stage_status["ingestion"] = f"error: {exc}"
            logger.exception("Pipeline ingestion stage failed")

        # -- Stage 2: extraction ---------------------------------------------
        try:
            extracted = self._extractor.extract_batch(signals)
            stage_status["extraction"] = "ok"
        except Exception as exc:  # noqa: BLE001
            stage_status["extraction"] = f"error: {exc}"
            logger.exception("Pipeline extraction stage failed")

        # -- Stage 3: risk scoring -------------------------------------------
        try:
            risk_scores = self._scoring.ranked(extracted)
            stage_status["scoring"] = "ok"
        except Exception as exc:  # noqa: BLE001
            stage_status["scoring"] = f"error: {exc}"
            logger.exception("Pipeline scoring stage failed")

        # -- Stage 4: scenario impact ----------------------------------------
        try:
            selected_id = scenario_id or self._auto_select_scenario(risk_scores)
            scenario = self._simulator.get_scenario(selected_id)
            impact = self._simulator.run(scenario)
            stage_status["scenario"] = "ok"
        except Exception as exc:  # noqa: BLE001
            stage_status["scenario"] = f"error: {exc}"
            logger.exception("Pipeline scenario stage failed")

        # -- Stage 5: procurement --------------------------------------------
        try:
            recommendations = self._recommender.recommend()
            stage_status["procurement"] = "ok"
        except Exception as exc:  # noqa: BLE001
            stage_status["procurement"] = f"error: {exc}"
            logger.exception("Pipeline procurement stage failed")

        linked_actions = self._build_linked_actions(risk_scores, recommendations)

        latency_ms = max(0, int((time.monotonic() - start) * 1000))

        return PipelineResult(
            signals=signals,
            risk_scores=risk_scores,
            impact=impact,
            recommendations=recommendations,
            linked_actions=linked_actions,
            latency_ms=latency_ms,
            data_source_modes=data_source_modes,
        )

    # -- internal helpers -----------------------------------------------------

    @staticmethod
    def _scenario_for_corridor(corridor_name: str) -> str:
        """Return the predefined scenario id modeling ``corridor_name`` (R9.3)."""
        return _CORRIDOR_SCENARIO.get(
            corridor_name.strip().lower(), _DEFAULT_SCENARIO_ID
        )

    def _auto_select_scenario(self, risk_scores: List[RiskScore]) -> str:
        """Pick the scenario for the highest "high"-band corridor.

        ``risk_scores`` is ranked highest-to-lowest, so the first corridor in the
        "high" band is the most at-risk one. When no corridor is "high" (or none
        exist), fall back to the default Hormuz scenario.
        """
        for score in risk_scores:
            if score.target_type == "corridor" and score.band == "high":
                return self._scenario_for_corridor(score.target)
        return _DEFAULT_SCENARIO_ID

    def _build_linked_actions(
        self,
        risk_scores: List[RiskScore],
        recommendations: List[ProcurementOption],
    ) -> List[dict]:
        """Build a linked action for each "high"-band corridor (R9.3).

        Every corridor whose score is in the "high" band gets an action dict
        referencing that corridor, its risk score, a recommended scenario id, and
        the top-ranked procurement option id (or ``None`` when there are no
        recommendations).
        """
        top_option_id = recommendations[0].id if recommendations else None

        actions: List[dict] = []
        for score in risk_scores:
            if score.target_type != "corridor" or score.band != "high":
                continue
            actions.append(
                {
                    "corridor": score.target,
                    "risk_score": score.score,
                    "recommended_scenario_id": self._scenario_for_corridor(
                        score.target
                    ),
                    "recommended_option_id": top_option_id,
                }
            )
        return actions
