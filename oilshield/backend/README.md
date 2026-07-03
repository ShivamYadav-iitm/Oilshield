# OilShield Backend

FastAPI backend for the OilShield Command Center - AI-driven energy supply chain
resilience for India's crude oil imports.

## Requirements

- Python 3.10+ (3.11 recommended)

## Local setup (Windows / PowerShell)

From this `backend/` folder:

```powershell
# 1. Create a virtual environment
python -m venv .venv

# 2. Activate it
.\.venv\Scripts\Activate.ps1

# 3. Install the app plus dev dependencies (tests)
pip install -e ".[dev]"

# 4. Run the server (auto-reload for development)
uvicorn app.main:app --reload

# 5. Open the interactive API docs
#    http://127.0.0.1:8000/docs
#    Health check: http://127.0.0.1:8000/health
```

## Run the tests

```powershell
pytest
```

## Run with Docker

```powershell
docker build -t oilshield-backend .
docker run -p 8000:8000 oilshield-backend
```

## Project layout

```
app/
  main.py       FastAPI app, CORS, health route
  api/          routers (added in later tasks)
  services/     ingestion, extraction, scoring, simulator, recommender, orchestrator
  providers/    datasource / llm / storage abstractions + implementations
  models/       shared Pydantic/SQLModel data models
  core/         config, constants, errors
  data/         bundled simulated JSON datasets
tests/
  unit/         example + edge-case tests
  properties/   property-based tests (Hypothesis)
```
