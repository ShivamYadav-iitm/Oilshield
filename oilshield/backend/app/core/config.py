"""Application configuration.

Centralizes runtime settings so services never read environment variables
directly. Two settings drive the system's "everything degrades gracefully"
behavior from the design:

- ``data_source_mode`` selects live feeds vs. bundled simulated data
  (Requirement 1.3 fallback / provenance).
- ``llm_provider`` selects the Groq/Gemini live extractors or the always-available
  deterministic fallback (Requirement 2.3), and ``llm_timeout_seconds`` bounds
  live LLM calls so ``Pipeline_Latency`` stays predictable.

Implementation note: ``pydantic-settings`` is intentionally NOT a dependency for
the hackathon MVP. To keep setup to zero we read from ``os.environ`` directly and
validate through a plain Pydantic ``BaseModel``. Swapping to ``BaseSettings``
later is a drop-in change behind ``get_settings()``.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Literal

from pydantic import BaseModel, Field, field_validator

DataSourceMode = Literal["live", "simulated"]
LLMProviderName = Literal["groq", "gemini", "deterministic"]

# Environment variable names, kept in one place so they are easy to document.
ENV_DATA_SOURCE_MODE = "DATA_SOURCE_MODE"
ENV_LLM_PROVIDER = "LLM_PROVIDER"
ENV_GROQ_API_KEY = "GROQ_API_KEY"
ENV_GEMINI_API_KEY = "GEMINI_API_KEY"
ENV_LLM_TIMEOUT_SECONDS = "LLM_TIMEOUT_SECONDS"

# Defaults chosen so the app runs fully offline out of the box: simulated data
# and the deterministic extractor require no API keys or network access.
DEFAULT_DATA_SOURCE_MODE: DataSourceMode = "simulated"
DEFAULT_LLM_PROVIDER: LLMProviderName = "deterministic"
DEFAULT_LLM_TIMEOUT_SECONDS: float = 3.0


class Settings(BaseModel):
    """Validated application settings.

    Values are normalized (trimmed, lower-cased for the mode/provider enums) and
    range-checked so an invalid configuration fails loudly at startup rather than
    surfacing as a confusing runtime error later.
    """

    data_source_mode: DataSourceMode = DEFAULT_DATA_SOURCE_MODE
    llm_provider: LLMProviderName = DEFAULT_LLM_PROVIDER
    groq_api_key: str | None = None
    gemini_api_key: str | None = None
    llm_timeout_seconds: float = Field(
        default=DEFAULT_LLM_TIMEOUT_SECONDS,
        gt=0,
        description="Timeout (seconds) for a single live LLM extraction call.",
    )

    model_config = {"frozen": True}

    @field_validator("data_source_mode", "llm_provider", mode="before")
    @classmethod
    def _normalize_enum(cls, value: object) -> object:
        """Accept case-insensitive / whitespace-padded enum values."""
        if isinstance(value, str):
            return value.strip().lower()
        return value

    @field_validator("groq_api_key", "gemini_api_key", mode="before")
    @classmethod
    def _blank_key_is_none(cls, value: object) -> object:
        """Treat empty / whitespace-only API keys as "not configured"."""
        if isinstance(value, str) and value.strip() == "":
            return None
        return value


def _load_from_environ(environ: dict[str, str] | None = None) -> Settings:
    """Build ``Settings`` from an environment mapping (defaults to ``os.environ``).

    Only variables that are actually present are passed through, so unset
    variables fall back to the model defaults rather than being read as empty
    strings.
    """
    env = os.environ if environ is None else environ

    raw: dict[str, object] = {}
    if ENV_DATA_SOURCE_MODE in env:
        raw["data_source_mode"] = env[ENV_DATA_SOURCE_MODE]
    if ENV_LLM_PROVIDER in env:
        raw["llm_provider"] = env[ENV_LLM_PROVIDER]
    if ENV_GROQ_API_KEY in env:
        raw["groq_api_key"] = env[ENV_GROQ_API_KEY]
    if ENV_GEMINI_API_KEY in env:
        raw["gemini_api_key"] = env[ENV_GEMINI_API_KEY]
    if ENV_LLM_TIMEOUT_SECONDS in env:
        raw["llm_timeout_seconds"] = env[ENV_LLM_TIMEOUT_SECONDS]

    return Settings(**raw)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached application settings, loaded once from the environment.

    Use this everywhere settings are needed. The cache makes it a cheap
    singleton; call ``get_settings.cache_clear()`` in tests to reload after
    mutating the environment.
    """
    return _load_from_environ()
