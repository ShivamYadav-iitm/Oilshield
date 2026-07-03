"""Shared API composition / dependency wiring.

This module is the single place where the OilShield service layer is composed
from the bundled datasets, so every router (signals, risk, scenarios,
procurement, pipeline) reuses the same known-targets list and the same service
instances instead of re-deriving them.

It provides:

- :func:`load_known_targets` -- build the canonical list of scoring targets
  (:class:`~app.services.KnownTarget`) from the bundled datasets: every corridor
  in ``corridors.json`` as a ``"corridor"`` target, plus every distinct
  ``supplier_country`` in ``routes.json`` / ``procurement_options.json`` as a
  ``"country"`` target.
- :func:`known_target_names` -- the flat list of target names handed to the
  :class:`~app.services.LLMExtractor` so it can map free text to a known target.
- Cached factories -- :func:`get_ingestion_service`, :func:`get_llm_extractor`,
  and :func:`get_risk_scoring_engine` -- returning process-wide singletons.

Design notes:

- **Side-effect free at import.** Nothing here touches the filesystem or builds
  a service at import time; datasets are read only when a loader/factory is
  first called, and the results are memoized with :func:`functools.lru_cache`.
- **Reuse.** Because the factories are cached, all routers share one ingestion
  service, one extractor, and one scoring engine, keeping the known-targets set
  consistent across the whole API.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Dict, List

from app.core.config import get_settings
from app.providers import LiveDataSource, build_llm_provider
from app.services import (
    KnownTarget,
    LLMExtractor,
    PipelineOrchestrator,
    ProcurementRecommender,
    RiskScoringEngine,
    ScenarioSimulator,
    SignalIngestionService,
)

__all__ = [
    "load_known_targets",
    "known_target_names",
    "get_ingestion_service",
    "get_llm_extractor",
    "get_risk_scoring_engine",
    "get_scenario_simulator",
    "get_procurement_recommender",
    "get_pipeline_orchestrator",
]

# Bundled datasets are resolved relative to this package (app/api -> app/data),
# not the process CWD, so the API works regardless of where it is launched from.
_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_CORRIDORS_PATH = _DATA_DIR / "corridors.json"
_ROUTES_PATH = _DATA_DIR / "routes.json"
_PROCUREMENT_PATH = _DATA_DIR / "procurement_options.json"


def _read_json(path: Path) -> dict:
    """Read and parse a bundled JSON dataset."""
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def load_known_targets() -> tuple[KnownTarget, ...]:
    """Build the canonical known-targets list from the bundled datasets.

    Corridors come from ``corridors.json`` (target_type ``"corridor"``); supplier
    countries are the distinct ``supplier_country`` values found across
    ``routes.json`` and ``procurement_options.json`` (target_type ``"country"``).
    Corridors are listed first, then countries, each in first-seen order with
    case-insensitive de-duplication.

    Returned as an immutable tuple so the memoized value cannot be mutated by a
    caller and shared across services safely.
    """
    targets: List[KnownTarget] = []
    seen: set[str] = set()

    def add(name: str, target_type: str) -> None:
        cleaned = (name or "").strip()
        key = cleaned.lower()
        if not cleaned or key in seen:
            return
        seen.add(key)
        targets.append(KnownTarget(name=cleaned, target_type=target_type))  # type: ignore[arg-type]

    # Corridors first.
    corridors = _read_json(_CORRIDORS_PATH).get("corridors", [])
    for corridor in corridors:
        add(corridor.get("name", ""), "corridor")

    # Supplier countries from routes and procurement options.
    routes = _read_json(_ROUTES_PATH).get("routes", [])
    for route in routes:
        add(route.get("supplier_country", ""), "country")

    options = _read_json(_PROCUREMENT_PATH).get("procurement_options", [])
    for option in options:
        add(option.get("supplier_country", ""), "country")

    return tuple(targets)


@lru_cache(maxsize=1)
def known_target_names() -> tuple[str, ...]:
    """The flat list of known target names (corridors + countries) for the LLM."""
    return tuple(target.name for target in load_known_targets())


@lru_cache(maxsize=1)
def get_ingestion_service() -> SignalIngestionService:
    """Return the process-wide :class:`SignalIngestionService` singleton.

    Provider selection is config-driven (Requirement 1.3): when
    ``data_source_mode == "live"`` a :class:`LiveDataSource` (seeded with the
    known-target names so it can hint targets) is used as the primary source,
    while the service always keeps the bundled :class:`SimulatedDataSource` as its
    guaranteed fallback. Under the default simulated configuration the service is
    built exactly as before -- no live provider is constructed.
    """
    settings = get_settings()
    if settings.data_source_mode == "live":
        primary = LiveDataSource(known_targets=list(known_target_names()))
        return SignalIngestionService(primary=primary, settings=settings)
    return SignalIngestionService()


@lru_cache(maxsize=1)
def get_llm_extractor() -> LLMExtractor:
    """Return the process-wide :class:`LLMExtractor`, seeded with known targets.

    The provider is chosen from configuration (Groq / Gemini when configured with
    an API key, otherwise the deterministic extractor). The extractor service
    itself still catches :class:`~app.core.errors.LLMError` and falls back to a
    deterministic result, so the deterministic path stays the guaranteed fallback
    (Requirement 2.3). Under defaults this yields a :class:`DeterministicExtractor`
    exactly as before.
    """
    return LLMExtractor(
        provider=build_llm_provider(get_settings()),
        known_targets=list(known_target_names()),
    )


@lru_cache(maxsize=1)
def get_risk_scoring_engine() -> RiskScoringEngine:
    """Return the process-wide :class:`RiskScoringEngine` over the known targets."""
    return RiskScoringEngine(load_known_targets())


@lru_cache(maxsize=1)
def get_scenario_simulator() -> ScenarioSimulator:
    """Return the process-wide :class:`ScenarioSimulator` singleton.

    Uses the simulator's default :class:`JsonFileScenarioRepository` so saved
    scenarios persist to a bundled JSON store with zero setup, and every router
    request shares the same catalog and repository.
    """
    return ScenarioSimulator()


@lru_cache(maxsize=1)
def get_procurement_recommender() -> ProcurementRecommender:
    """Return the process-wide :class:`ProcurementRecommender` singleton.

    Uses the recommender's default bundled catalog
    (``app/data/procurement_options.json``) so every router request shares one
    instance and the same deterministic recommendation set.
    """
    return ProcurementRecommender()


@lru_cache(maxsize=1)
def get_pipeline_orchestrator() -> PipelineOrchestrator:
    """Return the process-wide :class:`PipelineOrchestrator` singleton.

    Composes the orchestrator from the other cached service singletons so the
    full "signal to recommendation" pipeline reuses the same ingestion,
    extraction, scoring, simulator, and recommender instances (and therefore the
    same known-targets set) as the individual routers.
    """
    return PipelineOrchestrator(
        ingestion=get_ingestion_service(),
        extractor=get_llm_extractor(),
        scoring=get_risk_scoring_engine(),
        simulator=get_scenario_simulator(),
        recommender=get_procurement_recommender(),
    )
