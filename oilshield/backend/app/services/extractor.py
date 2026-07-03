"""LLM_Extractor service.

Turns normalized :class:`~app.models.Signal` records into structured
:class:`~app.models.ExtractedSignal` outputs by delegating the free-text
extraction to an :class:`~app.providers.base.LLMProvider` (Groq / Gemini live,
or the always-available :class:`~app.providers.llm.DeterministicExtractor`
fallback). The service is the seam described in the design's "Deterministic
core, probabilistic edges" principle: probabilistic extraction happens behind a
provider interface, and this service guarantees a well-formed, traceable result
regardless of what the provider does.

Responsibilities (Requirements 2.1-2.4):

- **Structured output (R2.1):** produce an ``ExtractedSignal`` with a
  ``target``/``target_type``, a ``risk_category``, and a ``severity`` in the
  inclusive range [0, 100]. Bounding is enforced by the model's validators.
- **Unclassified labeling (R2.2):** when the provider cannot map the text to a
  known corridor/country, the result carries ``target=None`` and
  ``classified=False`` so the scoring engine can exclude it.
- **Deterministic fallback (R2.3):** if a live provider raises ``LLMError`` (or
  times out), build a deterministic ``ExtractedSignal`` from the signal's
  ``raw_severity`` rather than failing the pipeline.
- **Traceability (R2.4):** the provider only sees ``text`` and ``known_targets``
  and therefore cannot know the originating signal's identity. This service
  attaches the real ``signal_id``, ``source``, and ``timestamp`` from the
  originating ``Signal`` onto every returned ``ExtractedSignal`` (both the
  provider's output and the fallback), so risk drivers remain traceable to
  evidence.

Requirements: 2.1, 2.2, 2.3, 2.4
"""

from __future__ import annotations

from typing import Iterable, List, Optional

from app.core.config import get_settings
from app.core.errors import LLMError
from app.models import ExtractedSignal, Signal
from app.providers import DeterministicExtractor, LLMProvider

__all__ = ["LLMExtractor"]

# risk_category used by the fallback output, where the provider never ran and so
# no category could be inferred from the text.
_FALLBACK_CATEGORY = "unknown"


def _default_provider() -> LLMProvider:
    """Select the default provider per configuration.

    Only the deterministic extractor is guaranteed to exist offline; the live
    Groq/Gemini providers are added later behind the same interface (task 26).
    Until then any configured provider degrades to the deterministic fallback so
    the service always has a working provider (Requirement 2.3).
    """
    # ``get_settings().llm_provider`` selects the provider; the live ones are not
    # yet available, so we return the deterministic extractor regardless. The
    # call keeps the config seam explicit for when live providers land.
    _ = get_settings().llm_provider
    return DeterministicExtractor()


class LLMExtractor:
    """Extracts structured, traceable signals via an ``LLMProvider``.

    The service owns the ``known_targets`` list (corridor + supplier-country
    names) passed to the provider, guarantees traceability fields are attached to
    every result, and provides a deterministic fallback on provider failure.
    """

    def __init__(
        self,
        provider: Optional[LLMProvider] = None,
        known_targets: Optional[Iterable[str]] = None,
    ) -> None:
        """Create the extractor service.

        Args:
            provider: The LLM provider to delegate extraction to. Defaults to the
                deterministic extractor selected per configuration (R2.3).
            known_targets: Corridor and supplier-country names the provider may
                map text to. Signals whose text matches none of these become
                unclassified (R2.2).
        """
        self._provider: LLMProvider = provider if provider is not None else _default_provider()
        self._known_targets: List[str] = list(known_targets) if known_targets else []
        # Lower-cased set for case-insensitive fallback classification.
        self._known_lower = frozenset(t.strip().lower() for t in self._known_targets if t)

    @property
    def known_targets(self) -> List[str]:
        """The corridor/country names this extractor recognizes."""
        return list(self._known_targets)

    def extract(self, signal: Signal) -> ExtractedSignal:
        """Extract a structured, traceable ``ExtractedSignal`` from ``signal``.

        Delegates the text extraction to the provider; on ``LLMError`` or a
        timeout, builds a deterministic fallback from ``signal.raw_severity``.
        Either way, the originating signal's traceability fields are attached
        before returning (R2.4).
        """
        try:
            extracted = self._provider.extract(signal.text_summary, self._known_targets)
        except (LLMError, TimeoutError):
            extracted = self._fallback(signal)
        return self._attach_traceability(extracted, signal)

    def extract_batch(self, signals: Iterable[Signal]) -> List[ExtractedSignal]:
        """Extract structured outputs for a batch of signals, in order."""
        return [self.extract(signal) for signal in signals]

    # -- internal helpers -----------------------------------------------------

    def _fallback(self, signal: Signal) -> ExtractedSignal:
        """Build a deterministic ``ExtractedSignal`` from the raw severity (R2.3).

        The signal is treated as classified only when its normalized ``target``
        is one of the known targets; otherwise it is unclassified so scoring
        excludes it (R2.2). ``severity`` is taken directly from the signal's
        ``raw_severity`` hint (already validated to [0, 100]).
        """
        classifiable = signal.target.strip().lower() in self._known_lower
        return ExtractedSignal(
            signal_id=signal.id,
            source=signal.source,
            timestamp=signal.timestamp,
            target=signal.target if classifiable else None,
            target_type=signal.target_type if classifiable else None,
            risk_category=_FALLBACK_CATEGORY,
            severity=signal.raw_severity,
            classified=classifiable,
        )

    @staticmethod
    def _attach_traceability(
        extracted: ExtractedSignal, signal: Signal
    ) -> ExtractedSignal:
        """Overwrite the provider's placeholder traceability with the real ones.

        The provider receives only ``text`` and ``known_targets`` and so fills
        ``signal_id``/``source``/``timestamp`` with placeholders. This attaches
        the originating signal's real values so evidence stays traceable (R2.4).
        """
        return extracted.model_copy(
            update={
                "signal_id": signal.id,
                "source": signal.source,
                "timestamp": signal.timestamp,
            }
        )
