"""Deterministic LLM-provider fallback for signal extraction.

``DeterministicExtractor`` implements the :class:`~app.providers.base.LLMProvider`
protocol without any network call or model. It is the guaranteed final fallback
in the extractor chain (Groq -> Gemini -> deterministic), so the pipeline always
completes offline and reproducibly during a live demo (design: "Deterministic
core, probabilistic edges"; Requirement 2.3).

Given a piece of signal ``text`` and the list of ``known_targets`` the system
recognizes, the extractor:

- scans the text (case-insensitively) for any known corridor/country name and,
  when one is found, sets ``target``/``target_type`` and marks the result
  ``classified=True`` (Requirement 2.1);
- when no known target is found, returns an *unclassified* result
  (``target=None``, ``classified=False``) so the scoring engine can exclude it
  (Requirement 2.2);
- always infers a ``risk_category`` from keyword rules and derives a
  ``severity`` in the inclusive range [0, 100] from a deterministic
  keyword-intensity heuristic (Requirement 2.1, design Property 3).

The traceability fields ``signal_id``, ``source``, and ``timestamp`` are *not*
known from ``text`` alone; the protocol only receives ``text`` and
``known_targets``. This extractor therefore fills them with neutral placeholders
and the calling ``LLM_Extractor`` service (task 8.1) attaches the originating
signal's real ``signal_id``/``source``/``timestamp`` for evidence traceability
(Requirement 2.4).

Requirements: 2.1, 2.2, 2.3
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Iterable, List, Optional

from app.core.errors import LLMError
from app.models import ExtractedSignal, TargetType

__all__ = ["DeterministicExtractor", "GroqProvider", "GeminiProvider"]

# Placeholder timestamp used when the extractor has no originating signal. The
# calling service overwrites this (and ``source``/``signal_id``) with the real
# signal's traceability fields (Requirement 2.4). A fixed epoch keeps the
# extractor's output fully deterministic.
_PLACEHOLDER_TIMESTAMP = datetime(1970, 1, 1, tzinfo=timezone.utc)

# Corridor names are the only "corridor" targets in the system; everything else
# in ``known_targets`` is treated as a supplier country. Matching is
# case-insensitive. Kept here (rather than imported from the data files) so the
# extractor stays a self-contained, dependency-light fallback.
_CORRIDOR_NAMES = frozenset(
    {
        "strait of hormuz",
        "red sea",
        "cape of good hope",
    }
)

# Risk-category keyword rules, checked in priority order. The first family with
# a keyword present in the text wins; if none match the category is "general".
_CATEGORY_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("sanctions", ("sanction", "price-cap", "price cap", "designation", "embargo", "ofac")),
    (
        "geopolitical",
        (
            "strike",
            "missile",
            "seize",
            "seized",
            "attack",
            "naval",
            "war",
            "conflict",
            "closure",
            "shutdown",
            "blockade",
            "tension",
            "escalate",
            "escalation",
        ),
    ),
    (
        "logistics",
        (
            "congestion",
            "transit",
            "reroute",
            "rerouting",
            "diversion",
            "divert",
            "voyage",
            "port",
            "backlog",
            "convoy",
            "idling",
            "delay",
            "capacity",
        ),
    ),
)

# Deterministic severity heuristic. Each keyword present in the text nudges the
# severity up (escalatory) or down (de-escalatory/easing) from a neutral base.
# The final value is clamped to [0, 100] so Property 3 holds for all inputs.
_BASE_SEVERITY: float = 20.0
_SEVERITY_KEYWORDS: dict[str, float] = {
    # high-intensity escalation
    "shutdown": 35.0,
    "blockade": 35.0,
    "closure": 30.0,
    "seize": 30.0,
    "seized": 30.0,
    "attack": 30.0,
    "missile": 30.0,
    "strike": 25.0,
    "sanction": 25.0,
    "war": 20.0,
    "disruption": 20.0,
    "escalate": 20.0,
    "escalation": 20.0,
    "tension": 18.0,
    # medium-intensity friction
    "reroute": 15.0,
    "rerouting": 15.0,
    "diversion": 15.0,
    "divert": 15.0,
    "congestion": 15.0,
    "delay": 12.0,
    "idling": 12.0,
    "premium": 8.0,
    "backlog": 10.0,
    "squeez": 12.0,
    # de-escalation / easing (negative contributions)
    "unaffected": -15.0,
    "reassure": -12.0,
    "eases": -10.0,
    "ease": -10.0,
    "steady": -10.0,
    "lower": -8.0,
    "clears": -8.0,
    "open": -6.0,
}


def _clamp(value: float, low: float, high: float) -> float:
    """Clamp ``value`` into the inclusive ``[low, high]`` range."""
    return max(low, min(high, value))


class DeterministicExtractor:
    """Rules-based, zero-network implementation of ``LLMProvider``.

    Fully deterministic: the same ``text`` and ``known_targets`` always yield the
    same ``ExtractedSignal``. This makes the offline demo reproducible and the
    behavior unit- and property-testable (design Property 3).
    """

    def __init__(
        self,
        *,
        corridor_names: Optional[Iterable[str]] = None,
        base_severity: float = _BASE_SEVERITY,
    ) -> None:
        # Normalize corridor names to lowercase for case-insensitive typing.
        names = _CORRIDOR_NAMES if corridor_names is None else corridor_names
        self._corridor_names = frozenset(n.strip().lower() for n in names)
        self._base_severity = base_severity

    # -- LLMProvider protocol -------------------------------------------------

    def extract(self, text: str, known_targets: List[str]) -> ExtractedSignal:
        """Extract a structured ``ExtractedSignal`` from ``text``.

        Scans ``text`` for any name in ``known_targets`` (case-insensitive
        substring match). When a target is found the result is classified and
        carries the matched target and its inferred type; otherwise it is
        unclassified (``target=None``). ``risk_category`` and a bounded
        ``severity`` are always produced.
        """
        safe_text = text or ""
        target = self._match_target(safe_text, known_targets)
        risk_category = self._infer_category(safe_text)
        severity = self._derive_severity(safe_text)

        if target is None:
            return ExtractedSignal(
                signal_id="",
                source="",
                timestamp=_PLACEHOLDER_TIMESTAMP,
                target=None,
                target_type=None,
                risk_category=risk_category,
                severity=severity,
                classified=False,
            )

        return ExtractedSignal(
            signal_id="",
            source="",
            timestamp=_PLACEHOLDER_TIMESTAMP,
            target=target,
            target_type=self._target_type(target),
            risk_category=risk_category,
            severity=severity,
            classified=True,
        )

    # -- internal helpers -----------------------------------------------------

    def _match_target(
        self, text: str, known_targets: List[str]
    ) -> Optional[str]:
        """Return the known target mentioned earliest in ``text``, else ``None``.

        Matching is a case-insensitive substring test. Ties (same earliest
        index) are broken by the order of ``known_targets`` so the result is
        deterministic.
        """
        lowered = text.lower()
        best_target: Optional[str] = None
        best_index: Optional[int] = None
        for candidate in known_targets:
            if not candidate:
                continue
            idx = lowered.find(candidate.lower())
            if idx == -1:
                continue
            if best_index is None or idx < best_index:
                best_index = idx
                best_target = candidate
        return best_target

    def _target_type(self, target: str) -> TargetType:
        """Classify a matched target as a corridor or a supplier country."""
        return "corridor" if target.strip().lower() in self._corridor_names else "country"

    def _infer_category(self, text: str) -> str:
        """Infer a ``risk_category`` from keyword rules; default ``"general"``."""
        lowered = text.lower()
        for category, keywords in _CATEGORY_RULES:
            if any(keyword in lowered for keyword in keywords):
                return category
        return "general"

    def _derive_severity(self, text: str) -> float:
        """Derive a bounded [0, 100] severity from keyword intensity."""
        lowered = text.lower()
        severity = self._base_severity
        for keyword, weight in _SEVERITY_KEYWORDS.items():
            if keyword in lowered:
                severity += weight
        return _clamp(severity, 0.0, 100.0)


# ---------------------------------------------------------------------------
# Live LLM providers (Groq primary, Gemini secondary)
# ---------------------------------------------------------------------------

# Endpoints for the free-tier chat APIs. Groq is OpenAI-compatible; Gemini uses
# Google's generateContent shape. Both are overridable for testing.
_GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
_GEMINI_URL_TEMPLATE = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
)

_DEFAULT_GROQ_MODEL = "llama-3.1-8b-instant"
_DEFAULT_GEMINI_MODEL = "gemini-1.5-flash"

# Instruction sent to the model: extract a small, strictly-typed JSON object.
_EXTRACTION_INSTRUCTION = (
    "You extract structured supply-chain risk data from a news snippet. "
    "Respond with ONLY a JSON object (no prose, no markdown) with exactly these "
    'keys: "target" (one of the provided known targets, matched exactly, or null '
    'if none apply), "risk_category" (one of "geopolitical", "sanctions", '
    '"logistics", or "general"), and "severity" (a number from 0 to 100). '
)


def _build_prompt(text: str, known_targets: List[str]) -> str:
    """Build the extraction prompt shared by both live providers."""
    targets = ", ".join(known_targets) if known_targets else "(none)"
    return (
        f"{_EXTRACTION_INSTRUCTION}\n"
        f"Known targets: {targets}\n"
        f"Snippet: {text or ''}"
    )


def _parse_extraction_json(content: str) -> dict:
    """Parse the model's textual response into a dict, tolerating fences/prose.

    Raises:
        LLMError: If no JSON object can be recovered from ``content``.
    """
    if not content:
        raise LLMError("LLM returned an empty response")
    stripped = content.strip()
    # Strip common markdown code fences (```json ... ```).
    if stripped.startswith("```"):
        stripped = re.sub(r"^```[a-zA-Z]*\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass
    # Fall back to the first {...} block found anywhere in the text.
    match = re.search(r"\{.*\}", stripped, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError as exc:
            raise LLMError(f"LLM response was not valid JSON: {exc}") from exc
    raise LLMError("LLM response did not contain a JSON object")


def _to_extracted_signal(
    data: dict, known_targets: List[str]
) -> ExtractedSignal:
    """Convert a parsed extraction dict into a validated ``ExtractedSignal``.

    Traceability fields are left as neutral placeholders; the ``LLM_Extractor``
    service attaches the originating signal's real id/source/timestamp (R2.4).

    Raises:
        LLMError: If the payload is unusable (e.g. severity is not numeric).
    """
    if not isinstance(data, dict):
        raise LLMError("LLM extraction payload was not a JSON object")

    raw_target = data.get("target")
    target: Optional[str] = None
    if isinstance(raw_target, str) and raw_target.strip():
        # Only accept a target the system actually knows (case-insensitive),
        # normalizing to the canonical known-target spelling.
        lowered = raw_target.strip().lower()
        for candidate in known_targets:
            if candidate.lower() == lowered:
                target = candidate
                break

    raw_category = data.get("risk_category")
    risk_category = (
        raw_category.strip() if isinstance(raw_category, str) and raw_category.strip()
        else "general"
    )

    try:
        severity = float(data.get("severity"))
    except (TypeError, ValueError) as exc:
        raise LLMError(f"LLM returned a non-numeric severity: {exc}") from exc
    severity = _clamp(severity, 0.0, 100.0)

    classified = target is not None
    target_type: Optional[TargetType] = None
    if classified:
        target_type = (
            "corridor" if target.strip().lower() in _CORRIDOR_NAMES else "country"
        )

    return ExtractedSignal(
        signal_id="",
        source="",
        timestamp=_PLACEHOLDER_TIMESTAMP,
        target=target,
        target_type=target_type,
        risk_category=risk_category,
        severity=severity,
        classified=classified,
    )


class GroqProvider:
    """Primary live ``LLMProvider`` backed by Groq's OpenAI-compatible API.

    Chosen as primary for its low latency (design). On any failure -- missing API
    key, HTTP error, timeout, or an unparseable response -- it raises
    :class:`LLMError` so the ``LLM_Extractor`` falls back to the
    :class:`DeterministicExtractor` (Requirement 2.3).
    """

    def __init__(
        self,
        *,
        api_key: Optional[str],
        model: str = _DEFAULT_GROQ_MODEL,
        timeout_seconds: float = 3.0,
        base_url: str = _GROQ_URL,
        client: Optional[object] = None,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._timeout_seconds = timeout_seconds
        self._base_url = base_url
        self._client = client

    def extract(self, text: str, known_targets: List[str]) -> ExtractedSignal:
        """Extract via Groq; raise :class:`LLMError` on any failure (R2.3)."""
        if not self._api_key:
            raise LLMError("Groq API key is not configured")

        import httpx

        prompt = _build_prompt(text, known_targets)
        body = {
            "model": self._model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }
        headers = {"Authorization": f"Bearer {self._api_key}"}

        try:
            response = self._post(base_url=self._base_url, json_body=body, headers=headers)
            response.raise_for_status()
            payload = response.json()
            content = payload["choices"][0]["message"]["content"]
        except LLMError:
            raise
        except Exception as exc:  # httpx errors, timeouts, KeyError, JSON errors
            raise LLMError(f"Groq extraction failed: {exc}") from exc

        return _to_extracted_signal(_parse_extraction_json(content), known_targets)

    def _post(self, *, base_url: str, json_body: dict, headers: dict):
        """Issue the POST request, reusing an injected client when provided."""
        import httpx

        if self._client is not None:
            return self._client.post(
                base_url, json=json_body, headers=headers, timeout=self._timeout_seconds
            )
        with httpx.Client(timeout=self._timeout_seconds) as client:
            return client.post(base_url, json=json_body, headers=headers)


class GeminiProvider:
    """Secondary live ``LLMProvider`` backed by Google's Gemini generateContent API.

    Behaves identically to :class:`GroqProvider` from the caller's perspective:
    any failure raises :class:`LLMError` so the extractor falls back to the
    deterministic path (Requirement 2.3).
    """

    def __init__(
        self,
        *,
        api_key: Optional[str],
        model: str = _DEFAULT_GEMINI_MODEL,
        timeout_seconds: float = 3.0,
        base_url: Optional[str] = None,
        client: Optional[object] = None,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._timeout_seconds = timeout_seconds
        self._base_url = base_url or _GEMINI_URL_TEMPLATE.format(model=model)
        self._client = client

    def extract(self, text: str, known_targets: List[str]) -> ExtractedSignal:
        """Extract via Gemini; raise :class:`LLMError` on any failure (R2.3)."""
        if not self._api_key:
            raise LLMError("Gemini API key is not configured")

        import httpx

        prompt = _build_prompt(text, known_targets)
        body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0, "responseMimeType": "application/json"},
        }
        params = {"key": self._api_key}

        try:
            response = self._post(json_body=body, params=params)
            response.raise_for_status()
            payload = response.json()
            content = payload["candidates"][0]["content"]["parts"][0]["text"]
        except LLMError:
            raise
        except Exception as exc:
            raise LLMError(f"Gemini extraction failed: {exc}") from exc

        return _to_extracted_signal(_parse_extraction_json(content), known_targets)

    def _post(self, *, json_body: dict, params: dict):
        """Issue the POST request, reusing an injected client when provided."""
        import httpx

        if self._client is not None:
            return self._client.post(
                self._base_url, json=json_body, params=params, timeout=self._timeout_seconds
            )
        with httpx.Client(timeout=self._timeout_seconds) as client:
            return client.post(self._base_url, json=json_body, params=params)
