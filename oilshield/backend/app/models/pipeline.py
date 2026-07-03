"""End-to-end pipeline result model.

``PipelineResult`` bundles every stage output of a single ``/pipeline/run`` so
the frontend can render the whole "signal to recommendation" flow at once. The
measured ``latency_ms`` (Pipeline_Latency, R9.2) is non-negative.

Requirements: 9.2, 9.3
"""

from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

from .procurement import ProcurementOption
from .risk import RiskScore
from .scenario import ImpactResult
from .signals import Signal


class PipelineResult(BaseModel):
    """Staged results plus provenance and latency for one full pipeline run."""

    signals: List[Signal] = Field(default_factory=list)
    risk_scores: List[RiskScore] = Field(default_factory=list)
    impact: Optional[ImpactResult] = None
    recommendations: List[ProcurementOption] = Field(default_factory=list)
    linked_actions: List[dict] = Field(
        default_factory=list,
        description='Surfaced when a corridor is "high" (R9.3)',
    )
    latency_ms: int = Field(description="Pipeline_Latency (R9.2)")
    data_source_modes: Dict[str, str] = Field(default_factory=dict)

    @field_validator("latency_ms")
    @classmethod
    def _check_latency(cls, value: int) -> int:
        if value < 0:
            raise ValueError(f"latency_ms must be >= 0, got {value}")
        return value
