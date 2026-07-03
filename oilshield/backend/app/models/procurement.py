"""Procurement option model.

A ``ProcurementOption`` combines the raw attributes provided by the bundled
``app/data/procurement_options.json`` (everything except ``recommendation_score``
and ``rationale``) with the two fields computed by the recommender. The
normalized attributes are bounded to [0, 1] and the recommendation score to
[0, 100] (Requirement 8.2) via validators.

Requirements: 8.2
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


def _validate_unit_interval(value: float, name: str) -> float:
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{name} must be within [0, 1], got {value}")
    return value


class ProcurementOption(BaseModel):
    """A scored procurement option with a plain-language rationale.

    The ``recommendation_score`` and ``rationale`` fields are computed by the
    recommender; they default to a neutral value / empty string so an option
    can be constructed directly from the bundled JSON attributes before
    scoring.
    """

    id: str
    supplier_country: str
    crude_grade: str
    tanker_route: str
    spot_price_usd_bbl: float
    tanker_availability: float = Field(description="0..1")
    port_congestion: float = Field(description="0..1 (higher = worse)")
    grade_compatibility: float = Field(description="0..1 (higher = better)")
    recommendation_score: float = Field(default=0.0, description="0..100")
    rationale: str = Field(default="")

    @field_validator("tanker_availability")
    @classmethod
    def _check_availability(cls, value: float) -> float:
        return _validate_unit_interval(value, "tanker_availability")

    @field_validator("port_congestion")
    @classmethod
    def _check_congestion(cls, value: float) -> float:
        return _validate_unit_interval(value, "port_congestion")

    @field_validator("grade_compatibility")
    @classmethod
    def _check_compatibility(cls, value: float) -> float:
        return _validate_unit_interval(value, "grade_compatibility")

    @field_validator("recommendation_score")
    @classmethod
    def _check_score(cls, value: float) -> float:
        if not 0.0 <= value <= 100.0:
            raise ValueError(
                f"recommendation_score must be within [0, 100], got {value}"
            )
        return value
