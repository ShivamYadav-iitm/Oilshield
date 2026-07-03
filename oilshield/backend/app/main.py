"""OilShield Command Center - FastAPI application entrypoint.

This is the minimal, immediately-runnable app skeleton. Routers, services, and
providers are added in later tasks; for now it exposes a health check so the
server boots and is demoable.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.pipeline import router as pipeline_router
from app.api.risk import router as risk_router
from app.api.procurement import router as procurement_router
from app.api.scenarios import router as scenarios_router
from app.api.signals import router as signals_router
from app.core.errors import register_error_handlers

app = FastAPI(
    title="OilShield Command Center API",
    description=(
        "Backend for the OilShield integrated resilience command center: "
        "live risk radar, disruption scenario simulator, and adaptive "
        "procurement recommendations for India's crude oil supply chain."
    ),
    version="0.1.0",
)

# CORS: the React + Vite frontend runs on a different origin during development
# (typically http://localhost:5173). Allow all origins for the hackathon MVP so
# the dashboard can call the API without extra setup. Tighten before production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register the typed error handler so any OilShieldError raised by routers or
# services is serialized into the consistent JSON envelope
# { "error": { "module", "message", "code" } } (Requirement 10.5).
register_error_handlers(app)

# API routers. Each router is a thin layer that delegates to the service layer
# composed in ``app.api.deps``. Registered after CORS and the error handler so
# those apply to every route.
app.include_router(signals_router)
app.include_router(risk_router)
app.include_router(scenarios_router)
app.include_router(procurement_router)
app.include_router(pipeline_router)


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    """Liveness probe. Returns a simple status payload so callers (and the
    frontend/demo) can confirm the server is up."""
    return {"status": "ok", "service": "oilshield-backend"}
