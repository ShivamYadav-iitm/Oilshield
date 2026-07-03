"""Signal ingestion and normalization service.

``SignalIngestionService`` is the first stage of the OilShield pipeline. It pulls
raw signals from every configured data source via a :class:`DataSourceProvider`,
normalizes each into a fully-populated :class:`Signal`, and records the
``Data_Source_Mode`` (live vs. simulated) for every source so the dashboard can
show data provenance (Requirement 1.6, 4.4).

Behavior (Requirements 1.1-1.6):

- **1.1** Iterate every configured source id and fetch its raw signals.
- **1.2** Normalize each ``RawSignal`` into a ``Signal`` carrying a stable id,
  source, timestamp, text summary, a resolved corridor/country target, and the
  raw severity hint.
- **1.3** If the primary (live) source raises :class:`DataSourceError`, fall back
  to the bundled :class:`SimulatedDataSource` for that source and record its mode
  as ``"simulated"``. This is a *recovery*, not a surfaced error.
- **1.4** If a raw signal cannot be normalized (no resolvable target, severity out
  of range, missing/unparseable required fields), raise :class:`NormalizationError`
  reporting the offending signal and fail the whole refresh -- bad data is never
  silently dropped or coerced.
- **1.6** Expose a per-source ``Data_Source_Mode`` map on the result.

This service depends only on the ``DataSourceProvider`` interface plus the
guaranteed :class:`SimulatedDataSource` fallback, so it runs fully offline.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from pydantic import ValidationError as PydanticValidationError

from app.core.config import Settings, get_settings
from app.core.errors import DataSourceError, NormalizationError
from app.models import DataSourceMode, RawSignal, Signal, TargetType
from app.providers import DataSourceProvider, SimulatedDataSource

__all__ = ["IngestionResult", "SignalIngestionService"]

# The corridors named in the design and bundled ``corridors.json``. A hinted
# target matching one of these (case-insensitively) is a "corridor"; every other
# non-empty hint is treated as a supplier "country".
_CORRIDOR_NAMES: frozenset[str] = frozenset(
    {"strait of hormuz", "red sea", "cape of good hope"}
)

# The data source ids bundled in ``app/data/signals.json``. Used as the default
# configured source list when a caller does not supply one.
DEFAULT_SOURCE_IDS: Tuple[str, ...] = ("news_feed", "sanctions_feed", "shipping_feed")


@dataclass(frozen=True)
class IngestionResult:
    """The outcome of a single ingestion refresh.

    Attributes:
        signals: The normalized signals across every configured source, in the
            order the sources were iterated.
        data_source_modes: Per-source ``Data_Source_Mode`` ("live" or
            "simulated"), so the dashboard can display data provenance
            (Requirements 1.6, 4.4).
    """

    signals: List[Signal] = field(default_factory=list)
    data_source_modes: Dict[str, DataSourceMode] = field(default_factory=dict)


class SignalIngestionService:
    """Fetch, normalize, and record provenance for raw signals (Requirement 1).

    The service is constructed with a *primary* data source and a *fallback*
    (always the bundled :class:`SimulatedDataSource`). When the primary raises
    :class:`DataSourceError` for a source, the service transparently loads that
    source from the fallback and marks it ``"simulated"`` (Requirement 1.3).
    """

    def __init__(
        self,
        primary: Optional[DataSourceProvider] = None,
        source_ids: Optional[Sequence[str]] = None,
        *,
        fallback: Optional[DataSourceProvider] = None,
        settings: Optional[Settings] = None,
    ) -> None:
        """Create the ingestion service.

        Args:
            primary: The primary data source. When omitted, the mode is chosen
                from ``settings.data_source_mode`` and the bundled
                :class:`SimulatedDataSource` is used (no live provider exists yet).
            source_ids: The configured source ids to ingest. Defaults to the
                bundled feed ids (news / sanctions / shipping).
            fallback: The fallback data source used on a primary failure. Defaults
                to :class:`SimulatedDataSource`.
            settings: Application settings; defaults to :func:`get_settings`.
        """
        resolved_settings = settings or get_settings()
        self._fallback: DataSourceProvider = fallback or SimulatedDataSource()
        self._source_ids: Tuple[str, ...] = tuple(source_ids or DEFAULT_SOURCE_IDS)

        if primary is None:
            # No live provider is available yet (see task 26.1), so we serve
            # everything from the simulated source and label it accordingly.
            self._primary: DataSourceProvider = self._fallback
            self._primary_mode: DataSourceMode = "simulated"
        else:
            self._primary = primary
            # A configured "live" mode means the injected primary is a live feed;
            # anything else is simulated provenance.
            self._primary_mode = (
                "live" if resolved_settings.data_source_mode == "live" else "simulated"
            )

    @property
    def source_ids(self) -> Tuple[str, ...]:
        """The configured source ids this service ingests."""
        return self._source_ids

    def refresh(self) -> IngestionResult:
        """Run a full data refresh across every configured source.

        Returns:
            An :class:`IngestionResult` with the normalized signals and the
            per-source ``Data_Source_Mode`` map.

        Raises:
            NormalizationError: If any raw signal cannot be normalized. The whole
                refresh fails and the offending signal is reported (Requirement 1.4).
            DataSourceError: If both the primary and the fallback fail to serve a
                source (e.g. an unknown source id).
        """
        signals: List[Signal] = []
        modes: Dict[str, DataSourceMode] = {}

        for source_id in self._source_ids:
            raw_signals, mode = self._fetch_source(source_id)
            modes[source_id] = mode
            for raw in raw_signals:
                signals.append(self._normalize(raw, source_id, mode))

        return IngestionResult(signals=signals, data_source_modes=modes)

    def _fetch_source(
        self, source_id: str
    ) -> Tuple[List[RawSignal], DataSourceMode]:
        """Fetch one source, falling back to simulated data on failure (R1.3)."""
        try:
            return list(self._primary.fetch_signals(source_id)), self._primary_mode
        except DataSourceError:
            # The primary (live) source is unreachable/errored: recover with the
            # bundled simulated data and mark this source's provenance accordingly.
            if self._primary is self._fallback:
                # Nothing to recover to -- the simulated source itself failed
                # (e.g. an unknown source id); surface the original error.
                raise
            return list(self._fallback.fetch_signals(source_id)), "simulated"

    def _normalize(
        self, raw: RawSignal, source_id: str, mode: DataSourceMode
    ) -> Signal:
        """Normalize one ``RawSignal`` into a ``Signal`` or fail loudly (R1.2, 1.4)."""
        target, target_type = self._resolve_target(raw.hinted_target)
        if target is None or target_type is None:
            raise NormalizationError(
                "Raw signal from source "
                f"'{source_id}' has no resolvable target (hinted_target="
                f"{raw.hinted_target!r}); cannot normalize into a Signal. "
                f"Offending signal: source={raw.source!r}, "
                f"timestamp={raw.timestamp.isoformat()}, text={raw.text!r}"
            )

        try:
            return Signal(
                id=self._signal_id(raw),
                source=raw.source,
                timestamp=raw.timestamp,
                text_summary=raw.text,
                target=target,
                target_type=target_type,
                raw_severity=raw.raw_severity,
                data_source_mode=mode,
            )
        except PydanticValidationError as exc:
            raise NormalizationError(
                "Raw signal from source "
                f"'{source_id}' failed normalization: {exc.errors()!r}. "
                f"Offending signal: source={raw.source!r}, "
                f"timestamp={raw.timestamp.isoformat()}, "
                f"raw_severity={raw.raw_severity!r}, text={raw.text!r}"
            ) from exc

    @staticmethod
    def _resolve_target(
        hinted_target: Optional[str],
    ) -> Tuple[Optional[str], Optional[TargetType]]:
        """Map a feed's hinted target to a (target, target_type) pair.

        A hint matching a known corridor name is a ``"corridor"``; any other
        non-empty hint is a supplier ``"country"``. A missing/blank hint yields
        ``(None, None)`` so the caller can fail the refresh (Requirement 1.4).
        """
        if hinted_target is None:
            return None, None
        cleaned = hinted_target.strip()
        if not cleaned:
            return None, None
        if cleaned.lower() in _CORRIDOR_NAMES:
            return cleaned, "corridor"
        return cleaned, "country"

    @staticmethod
    def _signal_id(raw: RawSignal) -> str:
        """Derive a stable, deterministic id from a raw signal's identity.

        The id is a hash of source + timestamp + text, so re-ingesting the same
        raw signal always yields the same ``Signal.id`` (idempotent refresh and
        stable traceability).
        """
        basis = f"{raw.source}|{raw.timestamp.isoformat()}|{raw.text}"
        digest = hashlib.sha1(basis.encode("utf-8")).hexdigest()[:12]
        return f"sig_{digest}"
