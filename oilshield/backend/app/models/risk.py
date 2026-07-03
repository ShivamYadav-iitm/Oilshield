"""Risk scoring data model.

A ``RiskScore`` is the deterministic aggregate of the classified signals for a
single target (corridor or supplier country). The score is bounded to the
inclusive range [0, 100] (Requirement 3.2) and carries the ids of the signals
that produced it for traceability (Requirement 4.3).

Requirements: 3.2
"""

from __future__ import annotations

from typing import List, Literal

from pydantic import BaseModel, Field, field_validator

RiskBand = Literal["low", "elevated", "high"]


class RiskScore(BaseModel):
    """Aggregate risk for one target, banded and traceable."""

    target: str
    target_type: Literal["corridor", "country"]
    score: float = Field(description="0..100 inclusive (R3.2)")
    band: RiskBand = Field(description="low / elevated / high (R3.4)")
    contributing_signal_ids: List[str] = Field(
        default_factory=list, description="Traceability (R4.3)"
    )

    @field_validator("score")
    @classmethod
    def _check_score(cls, value: float) -> float:
        if not 0.0 <= value <= 100.0:
            raise ValueError(f"score must be within [0, 100], got {value}")
        return value
