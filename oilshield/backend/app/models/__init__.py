"""Shared data models (Pydantic v2).

All model shapes are defined once here and mirrored in the frontend TypeScript
types. Field ranges are enforced by validators so invalid states are
unrepresentable (severity/score in [0, 100], availability/congestion/
compatibility in [0, 1], SPR days-of-cover >= 0, latency >= 0).
"""

from .pipeline import PipelineResult
from .procurement import ProcurementOption
from .risk import RiskBand, RiskScore
from .scenario import (
    ImpactPoint,
    ImpactResult,
    SavedScenario,
    Scenario,
    ScenarioAssumption,
)
from .signals import (
    DataSourceMode,
    ExtractedSignal,
    RawSignal,
    Signal,
    TargetType,
)

__all__ = [
    # signals
    "RawSignal",
    "Signal",
    "ExtractedSignal",
    "TargetType",
    "DataSourceMode",
    # risk
    "RiskScore",
    "RiskBand",
    # scenario
    "ScenarioAssumption",
    "Scenario",
    "ImpactPoint",
    "ImpactResult",
    "SavedScenario",
    # procurement
    "ProcurementOption",
    # pipeline
    "PipelineResult",
]
