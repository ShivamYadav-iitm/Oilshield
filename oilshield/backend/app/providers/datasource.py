"""Concrete data source providers.

``SimulatedDataSource`` reads the bundled ``app/data/signals.json`` feed and
returns the ``RawSignal`` records for a requested source id. It is the offline,
deterministic implementation of :class:`DataSourceProvider`: the whole pipeline
can run without any network access, and this same bundled data doubles as a
reproducible test fixture (design: "Everything degrades to simulated").

The JSON is grouped by source id keys (e.g. ``"news_feed"``,
``"sanctions_feed"``, ``"shipping_feed"``), each mapping to an array of raw
signal records shaped like :class:`app.models.RawSignal`.

Requirements: 1.5
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence

from app.core.errors import DataSourceError
from app.models import RawSignal

__all__ = ["SimulatedDataSource", "LiveDataSource"]

# The bundled dataset lives in ``app/data/signals.json``. Resolve it relative to
# this package (parent of ``providers``), not the process CWD, so the provider
# works regardless of where the server or tests are launched from.
_DEFAULT_SIGNALS_PATH = Path(__file__).resolve().parent.parent / "data" / "signals.json"


class SimulatedDataSource:
    """Serve ``RawSignal``s from the bundled JSON feed (Requirement 1.5).

    Implements the :class:`DataSourceProvider` protocol. The file is read and
    parsed lazily on first access and cached for subsequent calls.
    """

    def __init__(self, signals_path: Optional[Path] = None) -> None:
        """Create the source.

        Args:
            signals_path: Optional override for the bundled dataset location.
                Defaults to ``app/data/signals.json`` resolved against the
                package, so it is independent of the current working directory.
        """
        self._signals_path = Path(signals_path) if signals_path else _DEFAULT_SIGNALS_PATH
        self._feeds: Optional[Dict[str, List[dict]]] = None

    def _load_feeds(self) -> Dict[str, List[dict]]:
        """Read and cache the raw JSON feed mapping.

        Raises:
            DataSourceError: If the bundled file is missing or not valid JSON.
        """
        if self._feeds is None:
            try:
                raw = self._signals_path.read_text(encoding="utf-8")
                data = json.loads(raw)
            except FileNotFoundError as exc:
                raise DataSourceError(
                    f"Bundled signals dataset not found at {self._signals_path}"
                ) from exc
            except json.JSONDecodeError as exc:
                raise DataSourceError(
                    f"Bundled signals dataset is not valid JSON: {exc}"
                ) from exc
            if not isinstance(data, dict):
                raise DataSourceError(
                    "Bundled signals dataset must be an object keyed by source id"
                )
            self._feeds = data
        return self._feeds

    def fetch_signals(self, source_id: str) -> List[RawSignal]:
        """Return the bundled ``RawSignal``s for ``source_id``.

        Args:
            source_id: A feed key present in the dataset (e.g. ``"news_feed"``).

        Returns:
            The list of ``RawSignal`` records for that source.

        Raises:
            DataSourceError: If ``source_id`` is not a known feed in the dataset.
        """
        feeds = self._load_feeds()
        if source_id not in feeds:
            known = ", ".join(sorted(feeds)) or "<none>"
            raise DataSourceError(
                f"Unknown source_id '{source_id}'. Known sources: {known}"
            )
        return [RawSignal.model_validate(record) for record in feeds[source_id]]


# ---------------------------------------------------------------------------
# Live data source (GDELT / news feed)
# ---------------------------------------------------------------------------

# GDELT's public document API. It needs no API key and returns article records
# as JSON, which keeps the live path dependency-light for the hackathon MVP.
_DEFAULT_GDELT_URL = "https://api.gdeltproject.org/api/v2/doc/doc"

# Default query per bundled source id, so the live feed maps onto the same
# ``source_id`` seam the simulated source uses (news / sanctions / shipping).
_DEFAULT_QUERIES: Dict[str, str] = {
    "news_feed": "oil OR crude OR petroleum",
    "sanctions_feed": "oil sanctions OR oil embargo OR price cap",
    "shipping_feed": "oil tanker OR strait OR shipping lane",
}

# Neutral base severity for a live article, nudged up by escalation keywords in
# the headline. Kept small and self-contained so ``LiveDataSource`` needs no
# dependency on the extractor. The result is always clamped to [0, 100].
_LIVE_BASE_SEVERITY: float = 25.0
_LIVE_SEVERITY_KEYWORDS: Dict[str, float] = {
    "shutdown": 35.0,
    "blockade": 35.0,
    "closure": 30.0,
    "seize": 30.0,
    "seized": 30.0,
    "attack": 30.0,
    "missile": 30.0,
    "strike": 25.0,
    "sanction": 25.0,
    "embargo": 25.0,
    "war": 20.0,
    "conflict": 20.0,
    "disruption": 20.0,
    "escalate": 20.0,
    "tension": 18.0,
    "reroute": 15.0,
    "diversion": 15.0,
    "congestion": 15.0,
    "delay": 12.0,
}


def _clamp_0_100(value: float) -> float:
    """Clamp ``value`` into the inclusive [0, 100] severity range."""
    return max(0.0, min(100.0, value))


class LiveDataSource:
    """Fetch raw signals from a live news/GDELT feed (Requirements 1.1, 1.3).

    Implements the :class:`DataSourceProvider` protocol using ``httpx`` to query
    the GDELT document API. Articles are shaped into :class:`RawSignal` records;
    when a known target name is provided it is matched (case-insensitively)
    against the headline to populate ``hinted_target`` so the ingestion service
    can normalize the signal.

    Any HTTP, timeout, or parse failure is surfaced as :class:`DataSourceError`
    so the ingestion service transparently falls back to the bundled
    :class:`SimulatedDataSource` (Requirement 1.3). The provider never constructs
    or calls the network under the default (simulated) configuration -- it is
    only instantiated when ``data_source_mode == "live"``.
    """

    def __init__(
        self,
        *,
        queries: Optional[Mapping[str, str]] = None,
        known_targets: Optional[Sequence[str]] = None,
        base_url: str = _DEFAULT_GDELT_URL,
        timeout_seconds: float = 5.0,
        max_records: int = 25,
        client: Optional[object] = None,
    ) -> None:
        """Create the live data source.

        Args:
            queries: Mapping of ``source_id`` -> GDELT query string. Defaults to a
                sensible query per bundled source id.
            known_targets: Corridor/country names used to derive ``hinted_target``
                from an article headline. When omitted, ``hinted_target`` is None.
            base_url: The GDELT document API endpoint (overridable for testing).
            timeout_seconds: Per-request timeout for the live fetch.
            max_records: Maximum number of articles requested per source.
            client: Optional pre-built ``httpx.Client`` (mainly for testing). When
                omitted a client is created per request.
        """
        self._queries: Dict[str, str] = dict(queries or _DEFAULT_QUERIES)
        self._known_targets: List[str] = [t for t in (known_targets or []) if t]
        self._base_url = base_url
        self._timeout_seconds = timeout_seconds
        self._max_records = max_records
        self._client = client

    def fetch_signals(self, source_id: str) -> List[RawSignal]:
        """Fetch and shape live articles for ``source_id`` into ``RawSignal``s.

        Raises:
            DataSourceError: On any HTTP error, timeout, non-JSON body, or unusable
                payload, so ingestion can fall back to simulated data (R1.3).
        """
        # Import lazily so the module never requires ``httpx`` to be importable
        # under the default simulated configuration.
        import httpx

        query = self._queries.get(source_id, source_id)
        params = {
            "query": query,
            "format": "json",
            "mode": "artlist",
            "maxrecords": str(self._max_records),
            "sort": "datedesc",
        }

        try:
            if self._client is not None:
                response = self._client.get(
                    self._base_url, params=params, timeout=self._timeout_seconds
                )
            else:
                with httpx.Client(timeout=self._timeout_seconds) as client:
                    response = client.get(self._base_url, params=params)
            response.raise_for_status()
            payload = response.json()
        except DataSourceError:
            raise
        except Exception as exc:  # httpx errors, JSON decode, timeouts, etc.
            raise DataSourceError(
                f"Live data source '{source_id}' failed: {exc}"
            ) from exc

        return self._shape(payload, source_id)

    # -- internal helpers -----------------------------------------------------

    def _shape(self, payload: object, source_id: str) -> List[RawSignal]:
        """Map a GDELT JSON payload to ``RawSignal`` records defensively."""
        if not isinstance(payload, dict):
            raise DataSourceError(
                f"Live data source '{source_id}' returned an unexpected payload shape"
            )
        articles = payload.get("articles", [])
        if not isinstance(articles, list):
            raise DataSourceError(
                f"Live data source '{source_id}' returned no article list"
            )

        signals: List[RawSignal] = []
        for article in articles:
            if not isinstance(article, dict):
                continue
            text = (article.get("title") or "").strip()
            if not text:
                continue
            source = (article.get("domain") or "gdelt").strip() or "gdelt"
            timestamp = self._parse_timestamp(article.get("seendate"))
            signals.append(
                RawSignal(
                    source=source,
                    timestamp=timestamp,
                    text=text,
                    raw_severity=self._heuristic_severity(text),
                    hinted_target=self._match_target(text),
                )
            )
        return signals

    def _match_target(self, text: str) -> Optional[str]:
        """Return the first known target mentioned in ``text``, else ``None``."""
        lowered = text.lower()
        for candidate in self._known_targets:
            if candidate.lower() in lowered:
                return candidate
        return None

    @staticmethod
    def _heuristic_severity(text: str) -> float:
        """Derive a bounded [0, 100] severity from headline keywords."""
        lowered = text.lower()
        severity = _LIVE_BASE_SEVERITY
        for keyword, weight in _LIVE_SEVERITY_KEYWORDS.items():
            if keyword in lowered:
                severity += weight
        return _clamp_0_100(severity)

    @staticmethod
    def _parse_timestamp(value: object) -> datetime:
        """Parse a GDELT ``seendate`` (``YYYYMMDDTHHMMSSZ``); default to now (UTC)."""
        if isinstance(value, str) and value:
            for fmt in ("%Y%m%dT%H%M%SZ", "%Y-%m-%dT%H:%M:%SZ"):
                try:
                    return datetime.strptime(value, fmt).replace(tzinfo=timezone.utc)
                except ValueError:
                    continue
        return datetime.now(timezone.utc)
