"""Scenario configuration and impact result models.

Scenarios are made of explicit, testable ``ScenarioAssumption``s (Requirement
6.2). Running a scenario produces an ``ImpactResult`` whose ``timeline`` holds
one ``ImpactPoint`` per day. The SPR days-of-cover value can never be negative
(Requirement 6.4), which is enforced here so the invariant holds regardless of
how the cascade is computed.

Requirements: 6.4
"""

from __future__ import annotations

from typing import Dict, List

from pydantic import BaseModel, Field, field_validator


class ScenarioAssumption(BaseModel):
    """A single, explicit numeric assumption with its valid range."""

    key: str = Field(description='e.g. "corridor_closure_pct"')
    label: str
    value: float
    min_value: float
    max_value: float
    adjustable: bool
    unit: str = Field(description='e.g. "%", "kbd", "days"')

    @field_validator("max_value")
    @classmethod
    def _check_range(cls, max_value: float, info) -> float:
        min_value = info.data.get("min_value")
        if min_value is not None and max_value < min_value:
            raise ValueError(
                f"max_value ({max_value}) must be >= min_value ({min_value})"
            )
        return max_value


class Scenario(BaseModel):
    """A predefined disruption scenario and its assumption set."""

    id: str
    name: str = Field(description='e.g. "Strait of Hormuz partial closure"')
    corridor: str
    assumptions: List[ScenarioAssumption] = Field(default_factory=list)


class ImpactPoint(BaseModel):
    """One day of projected impact across the tracked indices."""

    day: int
    refinery_run_rate_pct: float
    fuel_price_index: float
    spr_days_of_cover: float = Field(description=">= 0 (R6.4)")
    gdp_index: float

    @field_validator("spr_days_of_cover")
    @classmethod
    def _check_spr_non_negative(cls, value: float) -> float:
        if value < 0.0:
            raise ValueError(
                f"spr_days_of_cover must be >= 0, got {value}"
            )
        return value


class ImpactResult(BaseModel):
    """The full timeline plus the assumptions that produced it."""

    scenario_id: str
    assumptions_used: List[ScenarioAssumption] = Field(
        default_factory=list,
        description="Displayed alongside results (R6.2)",
    )
    timeline: List[ImpactPoint] = Field(
        default_factory=list, description="Over scenario duration (R6.6)"
    )
    summary: Dict[str, float] = Field(
        default_factory=dict, description="End-state deltas"
    )


class SavedScenario(BaseModel):
    """A serialized scenario for the save/load round-trip (R7)."""

    version: int = Field(description="For compatibility checks (R7.3)")
    name: str
    assumptions: List[ScenarioAssumption] = Field(default_factory=list)
