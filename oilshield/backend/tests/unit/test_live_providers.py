"""Unit tests for the live providers and config-driven selection (Task 26).

These cover the fallback wiring guarantees:

- ``GroqProvider`` / ``GeminiProvider`` raise ``LLMError`` when no API key is
  configured, which triggers the extractor's deterministic fallback (R2.3).
- ``LiveDataSource`` raises ``DataSourceError`` on any fetch failure, which
  triggers the ingestion service's simulated fallback (R1.3).
- The config-driven factory keeps the deterministic / simulated defaults when
  nothing is configured (no live provider is constructed).
"""

import pytest

from app.core.config import Settings
from app.core.errors import DataSourceError, LLMError
from app.providers import (
    DeterministicExtractor,
    GeminiProvider,
    GroqProvider,
    LiveDataSource,
    SimulatedDataSource,
    build_data_source,
    build_llm_provider,
)

KNOWN_TARGETS = ["Strait of Hormuz", "Saudi Arabia"]


# --- LLM providers: missing key -> LLMError (R2.3) --------------------------


@pytest.mark.parametrize("provider_cls", [GroqProvider, GeminiProvider])
def test_llm_provider_raises_without_api_key(provider_cls):
    """A live LLM provider with no API key raises LLMError (extractor falls back)."""
    provider = provider_cls(api_key=None)
    with pytest.raises(LLMError):
        provider.extract("Strait of Hormuz tensions escalate", KNOWN_TARGETS)


@pytest.mark.parametrize("provider_cls", [GroqProvider, GeminiProvider])
def test_llm_provider_raises_on_blank_api_key(provider_cls):
    """An empty API key is treated as unconfigured and raises LLMError."""
    provider = provider_cls(api_key="")
    with pytest.raises(LLMError):
        provider.extract("some text", KNOWN_TARGETS)


# --- LiveDataSource: fetch failure -> DataSourceError (R1.3) ----------------


class _FailingClient:
    """A stand-in HTTP client whose GET always raises (network failure)."""

    def get(self, *args, **kwargs):
        raise RuntimeError("connection refused")


def test_live_data_source_raises_on_fetch_failure():
    """Any fetch error is surfaced as DataSourceError so ingestion can fall back."""
    source = LiveDataSource(client=_FailingClient())
    with pytest.raises(DataSourceError):
        source.fetch_signals("news_feed")


class _BadPayloadClient:
    """Returns a 200 response whose JSON body is the wrong shape."""

    class _Resp:
        def raise_for_status(self):
            return None

        def json(self):
            return ["not", "a", "dict"]

    def get(self, *args, **kwargs):
        return self._Resp()


def test_live_data_source_raises_on_bad_payload():
    """A well-formed HTTP response with an unusable body still raises DataSourceError."""
    source = LiveDataSource(client=_BadPayloadClient())
    with pytest.raises(DataSourceError):
        source.fetch_signals("news_feed")


class _OkClient:
    """Returns a realistic GDELT article payload."""

    class _Resp:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "articles": [
                    {
                        "title": "Strait of Hormuz closure fears escalate after attack",
                        "domain": "example.com",
                        "seendate": "20240115T101500Z",
                    }
                ]
            }

    def get(self, *args, **kwargs):
        return self._Resp()


def test_live_data_source_shapes_articles_into_raw_signals():
    """A valid payload is shaped into RawSignals with a matched hinted target."""
    source = LiveDataSource(client=_OkClient(), known_targets=KNOWN_TARGETS)
    signals = source.fetch_signals("news_feed")
    assert len(signals) == 1
    signal = signals[0]
    assert signal.source == "example.com"
    assert signal.hinted_target == "Strait of Hormuz"
    assert 0.0 <= signal.raw_severity <= 100.0
    # Escalation keywords ("closure", "attack", "escalate") lift severity above base.
    assert signal.raw_severity > 25.0


# --- Config-driven factory defaults -----------------------------------------


def test_factory_defaults_to_simulated_and_deterministic():
    """With default settings, no live provider is constructed."""
    settings = Settings()  # simulated + deterministic defaults
    assert isinstance(build_data_source(settings), SimulatedDataSource)
    assert isinstance(build_llm_provider(settings), DeterministicExtractor)


def test_factory_falls_back_to_deterministic_without_key():
    """Selecting groq/gemini without an API key still yields the deterministic path."""
    groq_no_key = Settings(llm_provider="groq")
    gemini_no_key = Settings(llm_provider="gemini")
    assert isinstance(build_llm_provider(groq_no_key), DeterministicExtractor)
    assert isinstance(build_llm_provider(gemini_no_key), DeterministicExtractor)


def test_factory_builds_live_providers_when_configured():
    """When live mode / a provider+key are configured, the live provider is built."""
    live_ds = build_data_source(Settings(data_source_mode="live"))
    assert isinstance(live_ds, LiveDataSource)

    groq = build_llm_provider(Settings(llm_provider="groq", groq_api_key="sk-test"))
    assert isinstance(groq, GroqProvider)

    gemini = build_llm_provider(
        Settings(llm_provider="gemini", gemini_api_key="g-test")
    )
    assert isinstance(gemini, GeminiProvider)
