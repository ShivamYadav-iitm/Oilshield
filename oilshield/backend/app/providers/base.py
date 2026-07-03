"""Abstraction interfaces for OilShield's external providers and storage.

Services depend on these :class:`typing.Protocol` interfaces, never on concrete
providers. This is the swap seam that lets the system degrade to simulated /
deterministic implementations offline and scale to live feeds, hosted models, or
a different database without touching business logic (design: "Abstraction
interfaces").

Concrete implementations built against these protocols:

- ``DataSourceProvider``  -> ``LiveDataSource`` / ``SimulatedDataSource``
- ``LLMProvider``         -> ``GroqProvider`` / ``GeminiProvider`` /
                             ``DeterministicExtractor``
- ``ScenarioRepository``  -> ``SqliteScenarioRepository`` /
                             ``JsonFileScenarioRepository``

Requirements: 1.1, 2.1, 7.1
"""

from __future__ import annotations

from typing import List, Protocol, runtime_checkable

from app.models import ExtractedSignal, RawSignal, SavedScenario

__all__ = [
    "DataSourceProvider",
    "LLMProvider",
    "ScenarioRepository",
]


@runtime_checkable
class DataSourceProvider(Protocol):
    """Fetches raw signals from a data source (live feed or bundled JSON).

    Implementations return signals exactly as the source provides them; the
    ingestion service is responsible for normalization.
    """

    def fetch_signals(self, source_id: str) -> List[RawSignal]:
        """Return the raw signals for the given ``source_id``.

        Raises:
            DataSourceError: If the source is unreachable or returns an error.
                The ingestion service catches this and falls back to
                ``SimulatedDataSource`` (Requirement 1.3).
        """
        ...


@runtime_checkable
class LLMProvider(Protocol):
    """Extracts structured signal data from unstructured text.

    The LLM is used *only* to turn free text into a structured
    ``ExtractedSignal``; all scoring/impact math stays deterministic elsewhere.
    """

    def extract(self, text: str, known_targets: List[str]) -> ExtractedSignal:
        """Extract a structured ``ExtractedSignal`` from ``text``.

        ``known_targets`` is the list of corridor/country names the extractor may
        map the text to; unmappable text yields an unclassified result.

        Raises:
            LLMError: If the provider fails or times out. The extractor catches
                this and falls back to the ``DeterministicExtractor`` built from
                the signal's raw severity (Requirement 2.3).
        """
        ...


@runtime_checkable
class ScenarioRepository(Protocol):
    """Persists and restores saved scenarios (Requirement 7)."""

    def save(self, record: SavedScenario) -> str:
        """Serialize and store ``record``; return its generated id."""
        ...

    def load(self, scenario_id: str) -> SavedScenario:
        """Load and deserialize the scenario stored under ``scenario_id``.

        Raises:
            ScenarioLoadError: If the stored representation is missing, malformed,
                or version-incompatible. No partial scenario is returned
                (Requirement 7.3).
        """
        ...
