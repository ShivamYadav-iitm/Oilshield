"""Procurement API router.

Exposes the Adaptive Procurement Recommendations endpoint, a thin delegate to
the shared :class:`ProcurementRecommender` (see :mod:`app.api.deps`):

- ``POST /procurement/recommend`` -- generate, score, filter, and rank the
  bundled procurement options, returning them ordered from highest to lowest
  ``recommendation_score`` (Requirement 8.4). Each option carries all of its
  attributes plus a plain-language rationale (R8.5); options below the
  ``MIN_COMPAT`` grade-compatibility floor are already excluded by the service
  (R8.1, R8.3).
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends

from app.api.deps import get_procurement_recommender
from app.services import ProcurementRecommender

router = APIRouter(prefix="/procurement", tags=["procurement"])


@router.post("/recommend")
def recommend_procurement(
    recommender: ProcurementRecommender = Depends(get_procurement_recommender),
) -> Dict[str, Any]:
    """Return ranked procurement recommendations (R8.1, R8.4, R8.5).

    Delegates to :meth:`ProcurementRecommender.recommend`, which loads the
    bundled catalog, scores each option, drops those below ``MIN_COMPAT``, and
    sorts the survivors by ``recommendation_score`` descending. The serialized
    options preserve that highest-to-lowest order (R8.4) and each includes its
    full attribute set and a non-empty rationale (R8.5).

    Returns:
        A JSON object with ``recommendations``: the ordered list of serialized
        :class:`ProcurementOption` records.
    """
    recommendations = recommender.recommend()
    return {
        "recommendations": [
            option.model_dump(mode="json") for option in recommendations
        ],
    }
