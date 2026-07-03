"""Scenario_Simulator service.

The Scenario_Simulator is the deterministic heart of the "what-if" module. It
does four things, each a pure function of its inputs so a judge can audit every
number and reproduce it offline:

1. **Catalog (R5.1, R5.2):** provides a fixed set of predefined disruption
   scenarios -- a Strait of Hormuz partial closure, an OPEC+ production cut, and
   a Red Sea shutdown -- each carrying its full :class:`ScenarioAssumption` list
   with valid ranges and adjustable flags.
2. **Assumption validation (R5.3-R5.5):** applies an edit to an adjustable
   assumption only when the submitted value is within that assumption's
   ``[min_value, max_value]`` range; otherwise it rejects the edit, keeps the
   previous valid value, and reports the valid range via ``ValidationError``.
3. **Impact cascade (R6.1-R6.4, R6.6):** turns a scenario's assumptions into a
   per-day :class:`ImpactResult` timeline using the documented, non-negative
   cascade constants in ``app/core/constants.py``. Monotonicity in closure and
   the SPR floor hold *by construction* (see ``run``).
4. **Save / restore (R7.1-R7.3):** serializes a configured scenario's name and
   assumption values into a versioned :class:`SavedScenario` through an injected
   :class:`ScenarioRepository`, and restores an identical scenario on load,
   rejecting malformed or version-incompatible representations.

Cascade (design "Scenario impact computation"), with every ``k_*`` constant
non-negative so the documented properties hold::

    supply_loss_fraction = clamp(
        corridor_import_share * (corridor_closure_pct / 100)
          + production_cut_kbd / TOTAL_IMPORT_KBD,
        0, 1)
    refinery_run_rate_pct(day) = clamp(100 - K_REF * supply_loss_fraction * 100, 0, 100)
    fuel_price_index(day)      = 100 * (1 + K_PRICE * supply_loss_fraction)
    spr_days_of_cover(day)     = max(0, spr_start_days - day * supply_loss_fraction / DRAWDOWN_DIVISOR)
    gdp_index(day)             = 100 * (1 - K_GDP * supply_loss_fraction * (day / duration_days))

Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 6.1, 6.2, 6.3, 6.4, 6.6, 7.1, 7.2, 7.3
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional

from app.core.constants import (
    DRAWDOWN_DIVISOR,
    K_GDP,
    K_PRICE,
    K_REF,
    TOTAL_IMPORT_KBD,
)
from app.core.errors import ScenarioLoadError, ValidationError
from app.models import (
    ImpactPoint,
    ImpactResult,
    SavedScenario,
    Scenario,
    ScenarioAssumption,
)
from app.providers import JsonFileScenarioRepository, ScenarioRepository
from app.providers.storage import CURRENT_SCENARIO_VERSION

__all__ = ["ScenarioSimulator"]


# Assumption keys used by the cascade. Centralized so the catalog builders and
# the impact computation cannot drift apart.
KEY_CLOSURE_PCT = "corridor_closure_pct"
KEY_PRODUCTION_CUT = "production_cut_kbd"
KEY_DURATION_DAYS = "duration_days"
KEY_IMPORT_SHARE = "corridor_import_share"
KEY_SPR_START = "spr_start_days"

# Per-corridor import shares (drawn from app/data/corridors.json). Displayed but
# typically non-adjustable, since they are structural facts about India's trade.
_HORMUZ_IMPORT_SHARE = 0.62
_RED_SEA_IMPORT_SHARE = 0.14

# Default starting SPR days-of-cover (~9-10 days for an India-style buffer).
_DEFAULT_SPR_START = 9.5


def _clamp(value: float, low: float, high: float) -> float:
    """Clamp ``value`` into the inclusive ``[low, high]`` range."""
    if value < low:
        return low
    if value > high:
        return high
    return value


def _is_real_number(value: object) -> bool:
    """True when ``value`` is a finite int/float (booleans excluded)."""
    if isinstance(value, bool):
        return False
    if not isinstance(value, (int, float)):
        return False
    return math.isfinite(float(value))


class ScenarioSimulator:
    """Predefined scenarios, assumption validation, impact cascade, save/load.

    The impact math is a pure, deterministic function of a scenario's
    assumptions; only :meth:`save`/:meth:`load` touch external state, through an
    injected :class:`ScenarioRepository` (defaulting to the JSON-file backend so
    the offline demo works with zero setup).
    """

    def __init__(self, repository: Optional[ScenarioRepository] = None) -> None:
        """Create the simulator.

        Args:
            repository: Storage backend for saved scenarios. Defaults to
                :class:`JsonFileScenarioRepository` so no database is required.
        """
        self._repository: ScenarioRepository = (
            repository if repository is not None else JsonFileScenarioRepository()
        )
        # Build the catalog once; every public accessor returns deep copies so
        # callers can freely mutate their scenario without corrupting the catalog.
        self._catalog: Dict[str, Scenario] = {
            scenario.id: scenario for scenario in self._build_catalog()
        }

    # -- Catalog (R5.1, R5.2) -------------------------------------------------

    def list_scenarios(self) -> List[Scenario]:
        """Return all predefined scenarios (deep copies), in catalog order."""
        return [scenario.model_copy(deep=True) for scenario in self._catalog.values()]

    def get_scenario(self, scenario_id: str) -> Scenario:
        """Return a deep copy of the predefined scenario with ``scenario_id``.

        Raises:
            ValidationError: If no predefined scenario has that id.
        """
        scenario = self._catalog.get(scenario_id)
        if scenario is None:
            raise ValidationError(
                f"Unknown scenario id '{scenario_id}'. Known ids: "
                f"{sorted(self._catalog)}."
            )
        return scenario.model_copy(deep=True)

    # -- Assumption validation (R5.3, R5.4, R5.5) -----------------------------

    def apply_assumption(
        self, scenario: Scenario, key: str, value: float
    ) -> Scenario:
        """Apply an edit to an adjustable assumption, validating the value.

        On success returns a new :class:`Scenario` whose assumption ``key`` holds
        the submitted ``value``. The input ``scenario`` is never mutated, so on
        rejection the caller's previous valid value is retained (R5.5).

        Args:
            scenario: The scenario to edit (left unchanged).
            key: The assumption ``key`` to update.
            value: The submitted value.

        Returns:
            A new scenario with the applied value (R5.4).

        Raises:
            ValidationError: If the key is unknown, the assumption is not
                adjustable, or the value is non-numeric or outside
                ``[min_value, max_value]``. The error's ``message`` includes the
                valid range, and ``valid_range``/``assumption_key`` attributes
                expose it programmatically (R5.5).
        """
        updated = scenario.model_copy(deep=True)
        target = next((a for a in updated.assumptions if a.key == key), None)

        if target is None:
            raise ValidationError(
                f"Scenario '{scenario.name}' has no assumption '{key}'."
            )

        if not target.adjustable:
            raise ValidationError(
                f"Assumption '{key}' is not adjustable.",
            )

        if not _is_real_number(value):
            err = ValidationError(
                f"Value {value!r} for '{key}' is not a valid number; "
                f"the valid range is [{target.min_value}, {target.max_value}]."
            )
            err.valid_range = (target.min_value, target.max_value)  # type: ignore[attr-defined]
            err.assumption_key = key  # type: ignore[attr-defined]
            raise err

        numeric = float(value)
        if not (target.min_value <= numeric <= target.max_value):
            err = ValidationError(
                f"Value {numeric} for '{key}' is outside the valid range "
                f"[{target.min_value}, {target.max_value}]."
            )
            err.valid_range = (target.min_value, target.max_value)  # type: ignore[attr-defined]
            err.assumption_key = key  # type: ignore[attr-defined]
            raise err

        # In range -> commit on the copy only (R5.4).
        target.value = numeric
        return updated

    # -- Impact cascade (R6.1-R6.4, R6.6) -------------------------------------

    def run(self, scenario: Scenario) -> ImpactResult:
        """Compute the deterministic impact timeline for ``scenario``.

        Builds exactly one :class:`ImpactPoint` per day over ``duration_days``
        (R6.1, R6.6), records the assumptions used (R6.2), and summarizes
        end-state deltas. Runs in O(duration_days) with duration bounded to 180,
        so it completes far within the 5-second budget (R6.5).

        Invariants that hold by construction:
        - SPR days-of-cover is monotonic non-increasing in closure (R6.3):
          ``supply_loss_fraction`` is non-decreasing in closure and enters the
          SPR drawdown term with a non-negative coefficient.
        - SPR days-of-cover is clamped at 0 (R6.4).
        - Refinery run rate stays in [0, 100]; indices stay non-negative.
        """
        share = self._value(scenario, KEY_IMPORT_SHARE, 0.0)
        closure_pct = self._value(scenario, KEY_CLOSURE_PCT, 0.0)
        production_cut = self._value(scenario, KEY_PRODUCTION_CUT, 0.0)
        spr_start = self._value(scenario, KEY_SPR_START, _DEFAULT_SPR_START)

        # duration_days is an integer horizon of at least one day.
        duration_days = int(self._value(scenario, KEY_DURATION_DAYS, 1.0))
        if duration_days < 1:
            duration_days = 1

        supply_loss_fraction = _clamp(
            share * (closure_pct / 100.0) + production_cut / TOTAL_IMPORT_KBD,
            0.0,
            1.0,
        )

        timeline: List[ImpactPoint] = []
        for day in range(1, duration_days + 1):
            run_rate = _clamp(100.0 - K_REF * supply_loss_fraction * 100.0, 0.0, 100.0)
            fuel_price = 100.0 * (1.0 + K_PRICE * supply_loss_fraction)
            spr = max(
                0.0,
                spr_start - day * supply_loss_fraction / DRAWDOWN_DIVISOR,
            )
            gdp = 100.0 * (
                1.0 - K_GDP * supply_loss_fraction * (day / duration_days)
            )
            timeline.append(
                ImpactPoint(
                    day=day,
                    refinery_run_rate_pct=run_rate,
                    fuel_price_index=fuel_price,
                    spr_days_of_cover=spr,
                    gdp_index=gdp,
                )
            )

        last = timeline[-1]
        summary: Dict[str, float] = {
            "supply_loss_fraction": supply_loss_fraction,
            "refinery_run_rate_pct_end": last.refinery_run_rate_pct,
            "refinery_run_rate_delta_pct": last.refinery_run_rate_pct - 100.0,
            "fuel_price_index_end": last.fuel_price_index,
            "fuel_price_index_delta": last.fuel_price_index - 100.0,
            "spr_days_of_cover_end": last.spr_days_of_cover,
            "spr_days_of_cover_delta": last.spr_days_of_cover - spr_start,
            "gdp_index_end": last.gdp_index,
            "gdp_index_delta": last.gdp_index - 100.0,
        }

        return ImpactResult(
            scenario_id=scenario.id,
            assumptions_used=[a.model_copy(deep=True) for a in scenario.assumptions],
            timeline=timeline,
            summary=summary,
        )

    # -- Save / restore (R7.1-R7.3) -------------------------------------------

    def save(self, scenario: Scenario) -> str:
        """Serialize ``scenario`` (name + assumption values) and store it.

        Returns:
            The generated id of the stored :class:`SavedScenario` (R7.1).
        """
        record = SavedScenario(
            version=CURRENT_SCENARIO_VERSION,
            name=scenario.name,
            assumptions=[a.model_copy(deep=True) for a in scenario.assumptions],
        )
        return self._repository.save(record)

    def load(self, scenario_id: str) -> Scenario:
        """Load a saved scenario and rebuild an identical :class:`Scenario`.

        The restored scenario has the same ``name`` and assumption values that
        were saved (round-trip, R7.2). When the saved name matches a predefined
        scenario, its ``id`` and ``corridor`` are recovered too; otherwise a
        fresh id is generated and the corridor is left blank.

        Raises:
            ScenarioLoadError: If the stored representation is missing, malformed,
                or version-incompatible (R7.3). Propagated from the repository.
        """
        saved: SavedScenario = self._repository.load(scenario_id)

        template = next(
            (s for s in self._catalog.values() if s.name == saved.name), None
        )
        restored_id = template.id if template is not None else f"loaded-{scenario_id}"
        restored_corridor = template.corridor if template is not None else ""

        return Scenario(
            id=restored_id,
            name=saved.name,
            corridor=restored_corridor,
            assumptions=[a.model_copy(deep=True) for a in saved.assumptions],
        )

    # -- internal helpers -----------------------------------------------------

    @staticmethod
    def _value(scenario: Scenario, key: str, default: float) -> float:
        """Return the current value of assumption ``key`` or ``default``."""
        for assumption in scenario.assumptions:
            if assumption.key == key:
                return float(assumption.value)
        return default

    def _build_catalog(self) -> List[Scenario]:
        """Construct the fixed predefined scenarios (R5.1)."""
        return [
            self._hormuz_partial_closure(),
            self._opec_production_cut(),
            self._red_sea_shutdown(),
        ]

    # Each builder returns a fresh Scenario. Adjustable flags match the
    # scenario's narrative: Hormuz/Red Sea drive closure percentage; OPEC+ drives
    # the production cut. Structural inputs (import share) are non-adjustable.

    def _hormuz_partial_closure(self) -> Scenario:
        return Scenario(
            id="hormuz_partial_closure",
            name="Strait of Hormuz partial closure",
            corridor="Strait of Hormuz",
            assumptions=[
                ScenarioAssumption(
                    key=KEY_CLOSURE_PCT,
                    label="Corridor closure",
                    value=50.0,
                    min_value=0.0,
                    max_value=100.0,
                    adjustable=True,
                    unit="%",
                ),
                ScenarioAssumption(
                    key=KEY_IMPORT_SHARE,
                    label="Corridor import share",
                    value=_HORMUZ_IMPORT_SHARE,
                    min_value=0.0,
                    max_value=1.0,
                    adjustable=False,
                    unit="fraction",
                ),
                ScenarioAssumption(
                    key=KEY_PRODUCTION_CUT,
                    label="OPEC+ production cut",
                    value=0.0,
                    min_value=0.0,
                    max_value=5000.0,
                    adjustable=False,
                    unit="kbd",
                ),
                ScenarioAssumption(
                    key=KEY_DURATION_DAYS,
                    label="Duration",
                    value=30.0,
                    min_value=1.0,
                    max_value=180.0,
                    adjustable=True,
                    unit="days",
                ),
                ScenarioAssumption(
                    key=KEY_SPR_START,
                    label="SPR starting days-of-cover",
                    value=_DEFAULT_SPR_START,
                    min_value=0.0,
                    max_value=120.0,
                    adjustable=True,
                    unit="days",
                ),
            ],
        )

    def _opec_production_cut(self) -> Scenario:
        return Scenario(
            id="opec_production_cut",
            name="OPEC+ production cut",
            corridor="Global / OPEC+",
            assumptions=[
                ScenarioAssumption(
                    key=KEY_PRODUCTION_CUT,
                    label="OPEC+ production cut",
                    value=2000.0,
                    min_value=0.0,
                    max_value=5000.0,
                    adjustable=True,
                    unit="kbd",
                ),
                ScenarioAssumption(
                    key=KEY_CLOSURE_PCT,
                    label="Corridor closure",
                    value=0.0,
                    min_value=0.0,
                    max_value=100.0,
                    adjustable=False,
                    unit="%",
                ),
                ScenarioAssumption(
                    key=KEY_IMPORT_SHARE,
                    label="Corridor import share",
                    value=0.0,
                    min_value=0.0,
                    max_value=1.0,
                    adjustable=False,
                    unit="fraction",
                ),
                ScenarioAssumption(
                    key=KEY_DURATION_DAYS,
                    label="Duration",
                    value=60.0,
                    min_value=1.0,
                    max_value=180.0,
                    adjustable=True,
                    unit="days",
                ),
                ScenarioAssumption(
                    key=KEY_SPR_START,
                    label="SPR starting days-of-cover",
                    value=_DEFAULT_SPR_START,
                    min_value=0.0,
                    max_value=120.0,
                    adjustable=True,
                    unit="days",
                ),
            ],
        )

    def _red_sea_shutdown(self) -> Scenario:
        return Scenario(
            id="red_sea_shutdown",
            name="Red Sea shutdown",
            corridor="Red Sea",
            assumptions=[
                ScenarioAssumption(
                    key=KEY_CLOSURE_PCT,
                    label="Corridor closure",
                    value=100.0,
                    min_value=0.0,
                    max_value=100.0,
                    adjustable=True,
                    unit="%",
                ),
                ScenarioAssumption(
                    key=KEY_IMPORT_SHARE,
                    label="Corridor import share",
                    value=_RED_SEA_IMPORT_SHARE,
                    min_value=0.0,
                    max_value=1.0,
                    adjustable=False,
                    unit="fraction",
                ),
                ScenarioAssumption(
                    key=KEY_PRODUCTION_CUT,
                    label="OPEC+ production cut",
                    value=0.0,
                    min_value=0.0,
                    max_value=5000.0,
                    adjustable=False,
                    unit="kbd",
                ),
                ScenarioAssumption(
                    key=KEY_DURATION_DAYS,
                    label="Duration",
                    value=45.0,
                    min_value=1.0,
                    max_value=180.0,
                    adjustable=True,
                    unit="days",
                ),
                ScenarioAssumption(
                    key=KEY_SPR_START,
                    label="SPR starting days-of-cover",
                    value=_DEFAULT_SPR_START,
                    min_value=0.0,
                    max_value=120.0,
                    adjustable=True,
                    unit="days",
                ),
            ],
        )
