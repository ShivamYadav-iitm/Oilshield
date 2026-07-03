"""Risk_Scoring_Engine service.

Turns a batch of structured :class:`~app.models.ExtractedSignal` outputs into a
:class:`~app.models.RiskScore` for **every** known target (corridor or supplier
country), banded and traceable. This is a pure, deterministic function of its
inputs -- one of the design's "deterministic core" services -- so the numbers a
judge sees are fully reproducible.

Behavior (Requirements 2.2, 3.1-3.4):

- **Completeness (R3.1):** emits exactly one ``RiskScore`` per known target,
  regardless of how many signals arrived. The known targets are supplied at
  construction time (corridor + supplier-country names with their types) rather
  than hardcoded, so the caller derives them from the bundled ``corridors.json``
  / ``routes.json`` datasets.
- **Bounded score (R3.2):** every ``RiskScore.score`` lies in the inclusive
  range [0, 100]. The aggregation is a *saturating* (noisy-OR) combination that
  cannot exceed 100 no matter how many high-severity signals accumulate.
- **Zero-default (R3.3):** a target with no classified contributing signals
  receives a score of exactly 0 (the empty aggregation).
- **Unclassified exclusion (R2.2):** signals with ``classified=False`` are
  dropped before aggregation, so they never change any score (Property 5).
- **Banding (R3.4):** each score is classified into "low" (0-33), "elevated"
  (34-66), or "high" (67-100) using the thresholds in ``core/constants.py``.

Aggregation rationale
---------------------
Each classified signal's ``severity`` (0-100) is read as a probability-like
fraction ``p = severity / 100``. The target's combined risk is the
complementary product (noisy-OR)::

    score = 100 * (1 - product(1 - p_i for each contributing signal))

Properties this gives us for free:

- **Bounded:** every factor ``(1 - p_i)`` is in [0, 1], so their product is in
  [0, 1] and the score is in [0, 100] (R3.2 / Property 7).
- **Zero-default:** with no signals the product is the empty product ``1``, so
  the score is ``0`` (R3.3 / Property 6).
- **Monotone & saturating:** adding a signal can only lower the product (raise
  the score), and the score approaches but never exceeds 100 -- extra corroborating
  signals raise risk with diminishing returns, which is intuitive for a risk
  indicator.
- **Order-independent:** multiplication commutes, so signal ordering never
  changes the result.

Requirements: 2.2, 3.1, 3.2, 3.3, 3.4
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Sequence, Tuple, Union

from app.core.constants import RISK_BAND_ELEVATED_MAX, RISK_BAND_LOW_MAX
from app.models import ExtractedSignal, RiskScore
from app.models.risk import RiskBand
from app.models.signals import TargetType

__all__ = ["KnownTarget", "RiskScoringEngine"]


@dataclass(frozen=True)
class KnownTarget:
    """A corridor or supplier country the engine must always score.

    Attributes:
        name: The canonical display name (e.g. ``"Strait of Hormuz"``,
            ``"Iraq"``). Emitted verbatim on the resulting ``RiskScore``.
        target_type: ``"corridor"`` or ``"country"``.
    """

    name: str
    target_type: TargetType


# A caller may pass either ``KnownTarget`` instances or ``(name, target_type)``
# tuples; both are normalized at construction.
KnownTargetInput = Union[KnownTarget, Tuple[str, TargetType]]


class RiskScoringEngine:
    """Aggregate classified signals into a banded ``RiskScore`` per known target.

    The set of known targets is fixed at construction (Requirement 3.1). Scoring
    is a pure function: calling :meth:`score` with the same inputs always yields
    the same outputs.
    """

    def __init__(self, known_targets: Iterable[KnownTargetInput]) -> None:
        """Create the engine over a fixed set of known targets.

        Args:
            known_targets: The corridors and supplier countries to always emit a
                score for. Each item is a :class:`KnownTarget` or a
                ``(name, target_type)`` tuple. Duplicate names (case-insensitive)
                are de-duplicated, keeping the first occurrence.
        """
        # Preserve caller order while de-duplicating by normalized name so the
        # output order is stable and predictable.
        self._targets: List[KnownTarget] = []
        self._by_norm: Dict[str, KnownTarget] = {}
        for item in known_targets:
            target = self._coerce(item)
            norm = self._normalize(target.name)
            if not norm or norm in self._by_norm:
                continue
            self._by_norm[norm] = target
            self._targets.append(target)

    @property
    def known_targets(self) -> List[KnownTarget]:
        """The de-duplicated known targets this engine scores, in order."""
        return list(self._targets)

    def score(self, extracted: Iterable[ExtractedSignal]) -> List[RiskScore]:
        """Compute one banded ``RiskScore`` for every known target.

        Unclassified signals (``classified=False``) and signals whose target is
        not a known target are ignored. Every known target appears in the result
        exactly once; those with no contributing signals score 0.

        Args:
            extracted: The structured extractor outputs to aggregate.

        Returns:
            One :class:`RiskScore` per known target, in the engine's target order.
        """
        buckets: Dict[str, List[ExtractedSignal]] = {norm: [] for norm in self._by_norm}

        for signal in extracted:
            # R2.2 / Property 5: unclassified signals never affect scoring.
            if not signal.classified or signal.target is None:
                continue
            norm = self._normalize(signal.target)
            bucket = buckets.get(norm)
            if bucket is None:
                # Classified, but not one of the known targets -> cannot
                # contribute to any emitted score.
                continue
            bucket.append(signal)

        results: List[RiskScore] = []
        for norm, target in self._by_norm.items():
            contributing = buckets[norm]
            value = self._aggregate([s.severity for s in contributing])
            results.append(
                RiskScore(
                    target=target.name,
                    target_type=target.target_type,
                    score=value,
                    band=self.classify_band(value),
                    contributing_signal_ids=[s.signal_id for s in contributing],
                )
            )
        return results

    def ranked(self, extracted: Iterable[ExtractedSignal]) -> List[RiskScore]:
        """Score all known targets and return them highest-to-lowest (R4.2).

        Ties preserve the engine's target order (Python's sort is stable).
        """
        return self.sort_by_score(self.score(extracted))

    # -- pure helpers ---------------------------------------------------------

    @staticmethod
    def sort_by_score(scores: Sequence[RiskScore]) -> List[RiskScore]:
        """Return ``scores`` ordered by ``score`` descending (non-increasing)."""
        return sorted(scores, key=lambda r: r.score, reverse=True)

    @staticmethod
    def classify_band(score: float) -> RiskBand:
        """Band a score in [0, 100] as low / elevated / high (R3.4, Property 8).

        Uses the inclusive lower-band maxima from ``core/constants.py``:
        ``<= RISK_BAND_LOW_MAX`` is "low", ``<= RISK_BAND_ELEVATED_MAX`` is
        "elevated", and anything higher is "high". This is total over [0, 100]
        with no gaps or overlaps at the boundaries.
        """
        if score <= RISK_BAND_LOW_MAX:
            return "low"
        if score <= RISK_BAND_ELEVATED_MAX:
            return "elevated"
        return "high"

    @staticmethod
    def _aggregate(severities: Sequence[float]) -> float:
        """Combine severities into a bounded [0, 100] score (see module docstring).

        Empty input yields exactly 0 (R3.3); otherwise a saturating noisy-OR that
        stays within [0, 100] (R3.2).
        """
        product = 1.0
        for severity in severities:
            fraction = severity / 100.0
            # Clamp defensively; model validators already bound severity to
            # [0, 100], but this keeps the math safe against any drift.
            if fraction < 0.0:
                fraction = 0.0
            elif fraction > 1.0:
                fraction = 1.0
            product *= 1.0 - fraction
        score = 100.0 * (1.0 - product)
        # Guard against floating-point excursions just outside the bounds.
        if score < 0.0:
            return 0.0
        if score > 100.0:
            return 100.0
        return score

    @staticmethod
    def _coerce(item: KnownTargetInput) -> KnownTarget:
        """Accept a ``KnownTarget`` or ``(name, target_type)`` tuple."""
        if isinstance(item, KnownTarget):
            return item
        name, target_type = item
        return KnownTarget(name=name, target_type=target_type)

    @staticmethod
    def _normalize(name: str) -> str:
        """Case-insensitive, whitespace-trimmed key for matching targets."""
        return name.strip().lower()
