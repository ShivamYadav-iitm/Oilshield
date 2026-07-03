"""Risk API router.

Exposes the Live Risk Radar's read endpoints:

- ``GET /risk/scores`` -- the current banded :class:`RiskScore` for every known
  target (corridor + supplier country), ranked from highest to lowest
  (Requirements 3.5, 4.2). The per-source ``Data_Source_Mode`` map is returned
  alongside for provenance (R4.4).
- ``GET /risk/{target}/signals`` -- the contributing normalized :class:`Signal`
  records (each with its source and timestamp) for a selected corridor/country
  (Requirement 4.3).

Both endpoints recompute from a fresh ingestion refresh within the request. The
ingestion service, extractor, and scoring engine are cached singletons (see
:mod:`app.api.deps`), but the *signals* they produce are not stored, so each
request runs ``ingestion.refresh() -> extractor.extract_batch() ->
scoring.score()``. Recomputing keeps the two endpoints consistent with each other
and ensures scores reflect the latest refresh (R3.5), which is essential for the
"selecting a target shows its contributing signals" trace to line up with the
scores shown in the ranked list.

Errors raised by ingestion (e.g. ``NormalizationError`` on malformed data, R1.4)
propagate to the app-wide exception handler, which serializes them into the
standard error envelope.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from fastapi import APIRouter, Depends

from app.api.deps import get_ingestion_service, get_llm_extractor, get_risk_scoring_engine
from app.models import RiskScore, Signal
from app.services import LLMExtractor, RiskScoringEngine, SignalIngestionService

router = APIRouter(prefix="/risk", tags=["risk"])


def _compute(
    ingestion: SignalIngestionService,
    extractor: LLMExtractor,
    scoring: RiskScoringEngine,
) -> Tuple[List[RiskScore], Dict[str, Signal], Dict[str, str]]:
    """Run one refresh -> extract -> score pass.

    Returns:
        A tuple of:
          - the ranked :class:`RiskScore`s (highest-to-lowest, R4.2),
          - a ``signal_id -> Signal`` map over the same refresh so contributing
            ids can be resolved back to normalized signals (R4.3),
          - the per-source ``Data_Source_Mode`` map for provenance (R4.4).
    """
    result = ingestion.refresh()
    signals_by_id: Dict[str, Signal] = {signal.id: signal for signal in result.signals}
    extracted = extractor.extract_batch(result.signals)
    ranked = scoring.ranked(extracted)
    return ranked, signals_by_id, dict(result.data_source_modes)


@router.get("/scores")
def get_risk_scores(
    ingestion: SignalIngestionService = Depends(get_ingestion_service),
    extractor: LLMExtractor = Depends(get_llm_extractor),
    scoring: RiskScoringEngine = Depends(get_risk_scoring_engine),
) -> Dict[str, Any]:
    """Return every target's banded ``RiskScore``, ranked highest-to-lowest.

    Runs a fresh ingestion + extraction + scoring pass so the scores reflect the
    latest data refresh (R3.5). Every known corridor and supplier country appears
    exactly once, ordered by score descending (R4.2).

    Returns:
        A JSON object with:
          - ``risk_scores``: the ranked :class:`RiskScore` records (serialized).
          - ``data_source_modes``: per-source provenance ("live"/"simulated", R4.4).
    """
    ranked, _signals_by_id, modes = _compute(ingestion, extractor, scoring)
    return {
        "risk_scores": [score.model_dump(mode="json") for score in ranked],
        "data_source_modes": modes,
    }


@router.get("/{target}/signals")
def get_target_signals(
    target: str,
    ingestion: SignalIngestionService = Depends(get_ingestion_service),
    extractor: LLMExtractor = Depends(get_llm_extractor),
    scoring: RiskScoringEngine = Depends(get_risk_scoring_engine),
) -> Dict[str, Any]:
    """Return the contributing signals for a selected corridor/country (R4.3).

    The ``target`` path segment is matched case-insensitively against the known
    targets. The response contains the normalized :class:`Signal` records that
    contributed to that target's score, each carrying its ``source`` and
    ``timestamp`` so risk drivers stay traceable to evidence.

    An unknown target (or a known target with no contributing signals) yields an
    empty ``signals`` list rather than an error, so the frontend detail drawer can
    render "no contributing signals" uniformly.

    Returns:
        A JSON object with:
          - ``target``: the resolved (canonical) target name, or the requested
            name if it is not a known target.
          - ``signals``: the contributing normalized signals (serialized), each
            with source and timestamp (R4.3).
          - ``data_source_modes``: per-source provenance ("live"/"simulated", R4.4).
    """
    ranked, signals_by_id, modes = _compute(ingestion, extractor, scoring)

    requested = target.strip().lower()
    matched = next(
        (score for score in ranked if score.target.strip().lower() == requested),
        None,
    )

    resolved_name = matched.target if matched is not None else target
    contributing: List[Signal] = []
    if matched is not None:
        # Resolve contributing ids back to the normalized signals from the same
        # refresh; guard against any id that is not present in the map.
        contributing = [
            signals_by_id[signal_id]
            for signal_id in matched.contributing_signal_ids
            if signal_id in signals_by_id
        ]

    return {
        "target": resolved_name,
        "signals": [signal.model_dump(mode="json") for signal in contributing],
        "data_source_modes": modes,
    }
