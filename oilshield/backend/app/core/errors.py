"""Typed error hierarchy and the FastAPI exception handler for OilShield.

Every backend failure that should reach the client is expressed as a subclass of
:class:`OilShieldError`. Each error carries three things the frontend needs to
render a module-scoped error (Requirement 10.5):

- ``module``: which part of the pipeline failed (e.g. "signal_ingestion"), so the
  dashboard can show the error in place of that module's loading indicator while
  leaving sibling modules untouched.
- ``message``: a human-readable description.
- ``code``: a stable machine-readable identifier (e.g. "LLM_ERROR") for the client.

The registered exception handler serializes any :class:`OilShieldError` into the
consistent JSON envelope ``{ "error": { "module", "message", "code" } }`` and maps
each error type to an appropriate HTTP status.
"""

from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

__all__ = [
    "OilShieldError",
    "DataSourceError",
    "LLMError",
    "NormalizationError",
    "ValidationError",
    "ScenarioLoadError",
    "oilshield_error_handler",
    "register_error_handlers",
]


class OilShieldError(Exception):
    """Base class for all OilShield domain errors.

    Subclasses set a default ``module``, ``code``, and ``http_status`` so callers
    can raise them with just a message, while still allowing any field to be
    overridden per-instance.
    """

    #: Default module label; subclasses override.
    module: str = "backend"
    #: Default machine-readable code; subclasses override.
    code: str = "OILSHIELD_ERROR"
    #: Default HTTP status this error maps to; subclasses override.
    http_status: int = status.HTTP_500_INTERNAL_SERVER_ERROR

    def __init__(
        self,
        message: str,
        *,
        module: str | None = None,
        code: str | None = None,
        http_status: int | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        if module is not None:
            self.module = module
        if code is not None:
            self.code = code
        if http_status is not None:
            self.http_status = http_status

    def to_envelope(self) -> dict[str, dict[str, str]]:
        """Serialize to the consistent JSON error envelope."""
        return {
            "error": {
                "module": self.module,
                "message": self.message,
                "code": self.code,
            }
        }


class DataSourceError(OilShieldError):
    """A live data source is unreachable or returned an error (R1.3).

    Typically caught inside the ingestion service, which falls back to simulated
    data rather than surfacing this to the user. Mapped to 502 if it does surface.
    """

    module = "signal_ingestion"
    code = "DATA_SOURCE_ERROR"
    http_status = status.HTTP_502_BAD_GATEWAY


class LLMError(OilShieldError):
    """An LLM provider failed or timed out (R2.3).

    Usually caught by the extractor, which falls back to a deterministic result.
    Mapped to 502 if it surfaces to the client.
    """

    module = "llm_extractor"
    code = "LLM_ERROR"
    http_status = status.HTTP_502_BAD_GATEWAY


class NormalizationError(OilShieldError):
    """A raw signal could not be normalized into a Signal record (R1.4).

    This is not recovered: the refresh fails so bad data cannot corrupt downstream
    scores. Mapped to 422 (unprocessable content).
    """

    module = "signal_ingestion"
    code = "NORMALIZATION_ERROR"
    http_status = status.HTTP_422_UNPROCESSABLE_ENTITY


class ValidationError(OilShieldError):
    """An assumption edit or input failed validation (R5.5).

    The previous value is retained; the valid range is communicated to the client.
    Mapped to 400 (bad request).
    """

    module = "scenario_simulator"
    code = "VALIDATION_ERROR"
    http_status = status.HTTP_400_BAD_REQUEST


class ScenarioLoadError(OilShieldError):
    """A stored scenario failed to deserialize (R7.3).

    No partial scenario is returned. Mapped to 400 (bad request).
    """

    module = "scenario_simulator"
    code = "SCENARIO_LOAD_ERROR"
    http_status = status.HTTP_400_BAD_REQUEST


async def oilshield_error_handler(
    _request: Request, exc: OilShieldError
) -> JSONResponse:
    """FastAPI exception handler that renders the JSON error envelope.

    Returns ``{ "error": { "module", "message", "code" } }`` with the HTTP status
    the specific error type maps to.
    """
    return JSONResponse(status_code=exc.http_status, content=exc.to_envelope())


def register_error_handlers(app: FastAPI) -> None:
    """Register the OilShield error handler on the given FastAPI app.

    Registering the base class covers every subclass, so all domain errors are
    serialized into the same envelope.
    """
    app.add_exception_handler(OilShieldError, oilshield_error_handler)
