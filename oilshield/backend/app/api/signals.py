"""Signals API router.

Exposes ``POST /signals/refresh``: runs the :class:`SignalIngestionService`
refresh and returns the normalized signals together with the per-source
``Data_Source_Mode`` map so the dashboard can show data provenance
(Requirements 1.1, 4.4).

The service is obtained from the shared composition module (:mod:`app.api.deps`)
so this router reuses the same ingestion service and known-targets wiring as the
rest of the API. Errors raised by ingestion (e.g. ``NormalizationError`` on
malformed data, R1.4) propagate to the app-wide exception handler, which
serializes them into the standard error envelope.
"""

from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Depends

from app.api.deps import get_ingestion_service
from app.services import SignalIngestionService

router = APIRouter(prefix="/signals", tags=["signals"])


@router.post("/refresh")
def refresh_signals(
    ingestion: SignalIngestionService = Depends(get_ingestion_service),
) -> Dict[str, Any]:
    """Run an ingestion refresh and return normalized signals + provenance.

    Returns:
        A JSON object with:
          - ``signals``: the normalized :class:`Signal` records (serialized).
          - ``data_source_modes``: per-source ``Data_Source_Mode`` ("live" or
            "simulated") so the dashboard can display data provenance (R4.4).
    """
    result = ingestion.refresh()
    signals: List[Dict[str, Any]] = [
        signal.model_dump(mode="json") for signal in result.signals
    ]
    return {
        "signals": signals,
        "data_source_modes": dict(result.data_source_modes),
    }
