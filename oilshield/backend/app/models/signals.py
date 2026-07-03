"""Signal data models for the ingestion -> extraction pipeline.

These models capture a signal as it moves through three stages:

- ``RawSignal``      -- exactly what a data source (live feed or bundled JSON)
                        provides, before any normalization.
- ``Signal``         -- a normalized, fully-populated signal with a resolved
                        target and provenance mode.
- ``ExtractedSignal``-- the structured output of the LLM / deterministic
                        extractor, carrying source and timestamp through for
                        traceability (Requirement 2.4).

Field ranges are enforced with validators so invalid states are
unrepresentable: severities are bounded to the inclusive range [0, 100].

Requirements: 2.1, 2.4
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

TargetType = Literal["corridor", "country"]
DataSourceMode = Literal["live", "simulated"]


def _validate_severity_0_100(value: float) -> float:
    """Reject severities outside the inclusive [0, 100] range (Req 2.1)."""
    if not 0.0 <= value <= 100.0:
        raise ValueError(f"severity must be within [0, 100], got {value}")
    return value


class RawSignal(BaseModel):
    """A signal exactly as a data source provides it, pre-normalization.

    Maps directly onto records in the bundled ``app/data/signals.json`` feed
    arrays (``source``, ``timestamp``, ``text``, ``raw_severity``,
    ``hinted_target``).
    """

    source: str
    timestamp: datetime
    text: str
    raw_severity: float = Field(description="0..100 source-provided severity hint")
    hinted_target: Optional[str] = Field(
        default=None,
        description="Corridor/country name if the feed provides one, else None",
    )

    @field_validator("raw_severity")
    @classmethod
    def _check_raw_severity(cls, value: float) -> float:
        return _validate_severity_0_100(value)


class Signal(BaseModel):
    """A normalized signal with a resolved target and provenance mode."""

    id: str
    source: str
    timestamp: datetime
    text_summary: str
    target: str = Field(description="Corridor or Supplier_Country name")
    target_type: TargetType
    raw_severity: float = Field(description="0..100")
    data_source_mode: DataSourceMode

    @field_validator("raw_severity")
    @classmethod
    def _check_raw_severity(cls, value: float) -> float:
        return _validate_severity_0_100(value)


class ExtractedSignal(BaseModel):
    """Structured extractor output; ``classified=False`` => excluded from scoring."""

    signal_id: str
    source: str = Field(description="Carried through for traceability (R2.4)")
    timestamp: datetime = Field(description="Carried through for traceability (R2.4)")
    target: Optional[str] = Field(
        default=None, description="None => unclassified"
    )
    target_type: Optional[TargetType] = None
    risk_category: str = Field(
        description='e.g. "geopolitical", "sanctions", "logistics"'
    )
    severity: float = Field(description="0..100")
    classified: bool = Field(
        description="False => excluded from scoring (R2.2)"
    )

    @field_validator("severity")
    @classmethod
    def _check_severity(cls, value: float) -> float:
        return _validate_severity_0_100(value)
