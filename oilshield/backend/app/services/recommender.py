"""Procurement_Recommender service.

The Procurement_Recommender turns the bundled catalog of crude-sourcing options
into a ranked, explainable set of recommendations. Like the rest of the
deterministic core it is a pure function of its inputs (the bundled JSON plus
the documented weights/thresholds in ``app/core/constants.py``), so every number
a judge sees can be audited and reproduced offline.

Pipeline (Requirement 8):

1. **Generate (R8.1):** load each option from
   ``app/data/procurement_options.json`` -- a Supplier_Country crude grade paired
   with a tanker route and its four raw attributes.
2. **Score (R8.2):** normalize each attribute to [0, 1] where 1 is best and
   combine them with the fixed, non-negative weights that sum to 1, scaling to
   ``recommendation_score`` in [0, 100]::

       price_score   = clamp((PRICE_CEILING - spot_price_usd_bbl)
                              / (PRICE_CEILING - PRICE_FLOOR), 0, 1)
       avail_score   = tanker_availability
       congest_score = 1 - port_congestion
       compat_score  = grade_compatibility
       recommendation_score = 100 * (W_PRICE*price_score + W_AVAIL*avail_score
                                     + W_CONGEST*congest_score + W_COMPAT*compat_score)

3. **Exclude (R8.3):** drop any option whose ``grade_compatibility`` is below
   ``MIN_COMPAT`` before ranking.
4. **Rank (R8.4):** return the surviving options sorted by
   ``recommendation_score`` descending.
5. **Explain (R8.5):** attach a plain-language rationale to each option that
   references its driving attributes.

Because all weights are non-negative and each sub-score is monotone in its
attribute, the score is monotone in every attribute: cheaper, more available,
less congested, more compatible options rank higher.

Requirements: 8.1, 8.2, 8.3, 8.4, 8.5
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List

from app.core.constants import (
    MIN_COMPAT,
    PRICE_CEILING,
    PRICE_FLOOR,
    W_AVAIL,
    W_COMPAT,
    W_CONGEST,
    W_PRICE,
)
from app.models import ProcurementOption

__all__ = ["ProcurementRecommender"]

# The bundled catalog lives in ``app/data/procurement_options.json``. Resolve it
# relative to this package (app/services -> app/data), not the process CWD, so
# the service works regardless of where the server or tests are launched from.
_DEFAULT_OPTIONS_PATH = (
    Path(__file__).resolve().parent.parent / "data" / "procurement_options.json"
)

# Top-level key under which the option records live in the bundled JSON.
_OPTIONS_KEY = "procurement_options"


def _clamp(value: float, low: float, high: float) -> float:
    """Clamp ``value`` into the inclusive ``[low, high]`` range."""
    if value < low:
        return low
    if value > high:
        return high
    return value


class ProcurementRecommender:
    """Generate, score, filter, and rank procurement options with rationales.

    The recommendation math is a pure, deterministic function of the bundled
    catalog and the documented constants; nothing here touches external state.
    """

    def __init__(self, options_path: Path | None = None) -> None:
        """Create the recommender.

        Args:
            options_path: Optional override for the bundled catalog location.
                Defaults to ``app/data/procurement_options.json`` resolved
                against the package, so it is independent of the current working
                directory.
        """
        self._options_path: Path = (
            options_path if options_path is not None else _DEFAULT_OPTIONS_PATH
        )

    # -- public API -----------------------------------------------------------

    def recommend(self) -> List[ProcurementOption]:
        """Return scored, filtered, ranked recommendations (R8.1-R8.5).

        Loads the bundled catalog, computes each option's
        ``recommendation_score`` in [0, 100], excludes options whose
        ``grade_compatibility`` is below ``MIN_COMPAT`` (R8.3), and returns the
        survivors sorted by ``recommendation_score`` descending (R8.4), each
        carrying a non-empty plain-language rationale (R8.5).
        """
        scored: List[ProcurementOption] = []
        for raw in self._load_raw_options():
            # Exclusion first (R8.3): options below the compatibility floor are
            # dropped before scoring/ranking and never surface to the user.
            if float(raw["grade_compatibility"]) < MIN_COMPAT:
                continue
            scored.append(self._score_option(raw))

        # Rank by score descending (R8.4). ``sorted`` is stable, so options that
        # tie on score keep their catalog order for a deterministic result.
        scored.sort(key=lambda option: option.recommendation_score, reverse=True)
        return scored

    # -- internal helpers -----------------------------------------------------

    def _load_raw_options(self) -> List[dict]:
        """Read the bundled catalog and return the raw option records (R8.1)."""
        with self._options_path.open(encoding="utf-8") as handle:
            payload = json.load(handle)
        return list(payload[_OPTIONS_KEY])

    def _score_option(self, raw: dict) -> ProcurementOption:
        """Build a fully-populated, scored :class:`ProcurementOption` (R8.2, R8.5)."""
        spot_price = float(raw["spot_price_usd_bbl"])
        availability = float(raw["tanker_availability"])
        congestion = float(raw["port_congestion"])
        compatibility = float(raw["grade_compatibility"])

        # Normalize each attribute to [0, 1] where 1 is best.
        price_score = _clamp(
            (PRICE_CEILING - spot_price) / (PRICE_CEILING - PRICE_FLOOR), 0.0, 1.0
        )
        avail_score = availability
        congest_score = 1.0 - congestion
        compat_score = compatibility

        # Weighted sum scaled to [0, 100]. Weights are non-negative and sum to 1
        # (enforced in constants), and every sub-score is in [0, 1], so the
        # result is guaranteed to land in [0, 100].
        recommendation_score = 100.0 * (
            W_PRICE * price_score
            + W_AVAIL * avail_score
            + W_CONGEST * congest_score
            + W_COMPAT * compat_score
        )
        # Guard against floating-point drift pushing the score a hair outside
        # [0, 100], which the model validator would otherwise reject.
        recommendation_score = _clamp(recommendation_score, 0.0, 100.0)

        rationale = self._build_rationale(
            supplier_country=str(raw["supplier_country"]),
            crude_grade=str(raw["crude_grade"]),
            spot_price=spot_price,
            price_score=price_score,
            avail_score=avail_score,
            congest_score=congest_score,
            compat_score=compat_score,
        )

        return ProcurementOption(
            id=str(raw["id"]),
            supplier_country=str(raw["supplier_country"]),
            crude_grade=str(raw["crude_grade"]),
            tanker_route=str(raw["tanker_route"]),
            spot_price_usd_bbl=spot_price,
            tanker_availability=availability,
            port_congestion=congestion,
            grade_compatibility=compatibility,
            recommendation_score=recommendation_score,
            rationale=rationale,
        )

    @staticmethod
    def _build_rationale(
        *,
        supplier_country: str,
        crude_grade: str,
        spot_price: float,
        price_score: float,
        avail_score: float,
        congest_score: float,
        compat_score: float,
    ) -> str:
        """Compose a plain-language rationale citing the driving attributes (R8.5).

        The rationale leads with the option's identity, then names its strongest
        and weakest normalized attributes so a procurement officer can see, in
        words, why it ranks where it does.
        """
        # Map each normalized sub-score to a human-friendly attribute phrase.
        attributes = {
            "price": (price_score, f"an attractive spot price near ${spot_price:.0f}/bbl"),
            "availability": (avail_score, "strong tanker availability"),
            "congestion": (congest_score, "low port congestion"),
            "compatibility": (compat_score, "high refinery grade compatibility"),
        }
        ranked = sorted(attributes.values(), key=lambda item: item[0], reverse=True)

        strongest_phrase = ranked[0][1]
        second_phrase = ranked[1][1]

        # Weakest attribute becomes a caveat when it is a genuine soft spot.
        weakest_score, weakest_desc = ranked[-1]
        weak_phrases = {
            "an attractive spot price near ${:.0f}/bbl".format(spot_price): (
                "a higher spot price"
            ),
            "strong tanker availability": "tighter tanker availability",
            "low port congestion": "heavier port congestion",
            "high refinery grade compatibility": "weaker grade compatibility",
        }

        lead = (
            f"{crude_grade} from {supplier_country} scores well on "
            f"{strongest_phrase} and {second_phrase}"
        )
        if weakest_score < 0.6:
            caveat = weak_phrases.get(weakest_desc, "some weaker attributes")
            return f"{lead}, though it is held back by {caveat}."
        return f"{lead}, with no major weaknesses across its attributes."
