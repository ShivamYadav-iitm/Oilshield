"""Config-driven provider selection.

This is the single place that turns application :class:`~app.core.config.Settings`
into concrete provider instances, keeping the "everything degrades gracefully"
policy from the design in one spot:

- :func:`build_data_source` returns a live :class:`LiveDataSource` only when
  ``data_source_mode == "live"``; otherwise the bundled
  :class:`SimulatedDataSource`. Even in live mode the ingestion service keeps a
  :class:`SimulatedDataSource` fallback, so an unreachable live feed degrades to
  simulated data (Requirement 1.3).
- :func:`build_llm_provider` returns :class:`GroqProvider` /
  :class:`GeminiProvider` only when the selected provider is configured *and*
  its API key is present; otherwise the always-available
  :class:`DeterministicExtractor`. The live providers themselves also raise
  :class:`~app.core.errors.LLMError` on failure, so the extractor's deterministic
  fallback remains the guaranteed final path (Requirement 2.3).

Under the default configuration (simulated data + deterministic LLM) neither
live provider is constructed, so no network client is ever created.

Requirements: 1.3, 2.3
"""

from __future__ import annotations

from typing import Optional, Sequence

from app.core.config import Settings, get_settings
from app.providers.base import DataSourceProvider, LLMProvider
from app.providers.datasource import LiveDataSource, SimulatedDataSource
from app.providers.llm import DeterministicExtractor, GeminiProvider, GroqProvider

__all__ = ["build_data_source", "build_llm_provider"]


def build_data_source(
    settings: Optional[Settings] = None,
    *,
    known_targets: Optional[Sequence[str]] = None,
) -> DataSourceProvider:
    """Return the configured data source provider.

    Args:
        settings: Application settings; defaults to :func:`get_settings`.
        known_targets: Corridor/country names passed to a live source so it can
            derive ``hinted_target`` from article headlines.

    Returns:
        A :class:`LiveDataSource` when ``data_source_mode == "live"``, otherwise a
        :class:`SimulatedDataSource`. The ingestion service always keeps a
        simulated fallback regardless (Requirement 1.3).
    """
    resolved = settings or get_settings()
    if resolved.data_source_mode == "live":
        return LiveDataSource(known_targets=known_targets)
    return SimulatedDataSource()


def build_llm_provider(settings: Optional[Settings] = None) -> LLMProvider:
    """Return the configured LLM provider, guaranteeing a deterministic fallback.

    Groq (primary) and Gemini (secondary) are selected only when configured and
    their API key is present; anything else -- including a selected live provider
    with a missing key -- resolves to the :class:`DeterministicExtractor` so the
    pipeline always has a working provider (Requirement 2.3).
    """
    resolved = settings or get_settings()

    if resolved.llm_provider == "groq" and resolved.groq_api_key:
        return GroqProvider(
            api_key=resolved.groq_api_key,
            timeout_seconds=resolved.llm_timeout_seconds,
        )
    if resolved.llm_provider == "gemini" and resolved.gemini_api_key:
        return GeminiProvider(
            api_key=resolved.gemini_api_key,
            timeout_seconds=resolved.llm_timeout_seconds,
        )
    return DeterministicExtractor()
