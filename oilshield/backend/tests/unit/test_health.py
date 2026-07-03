"""Verify the FastAPI app imports and the GET /health route works."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_app_imports():
    """The app object should be importable and configured."""
    assert app.title == "OilShield Command Center API"


def test_health_route_returns_ok():
    """GET /health returns 200 with an ok status payload."""
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "oilshield-backend"
