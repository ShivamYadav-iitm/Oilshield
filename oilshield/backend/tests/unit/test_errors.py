"""Tests for the typed error hierarchy and the FastAPI exception handler."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.errors import (
    DataSourceError,
    LLMError,
    NormalizationError,
    OilShieldError,
    ScenarioLoadError,
    ValidationError,
    register_error_handlers,
)

ALL_ERRORS = [
    DataSourceError,
    LLMError,
    NormalizationError,
    ValidationError,
    ScenarioLoadError,
]


@pytest.mark.parametrize("error_cls", ALL_ERRORS)
def test_all_errors_subclass_base(error_cls):
    """Every domain error is an OilShieldError (so one handler covers them all)."""
    assert issubclass(error_cls, OilShieldError)
    assert issubclass(error_cls, Exception)


@pytest.mark.parametrize("error_cls", ALL_ERRORS)
def test_error_carries_module_message_code(error_cls):
    """Each error exposes module, message, and code with a defined HTTP status."""
    err = error_cls("something failed")
    assert err.message == "something failed"
    assert isinstance(err.module, str) and err.module
    assert isinstance(err.code, str) and err.code
    assert isinstance(err.http_status, int)


@pytest.mark.parametrize("error_cls", ALL_ERRORS)
def test_envelope_shape(error_cls):
    """to_envelope produces { 'error': { module, message, code } }."""
    err = error_cls("boom")
    envelope = err.to_envelope()
    assert set(envelope) == {"error"}
    assert set(envelope["error"]) == {"module", "message", "code"}
    assert envelope["error"]["message"] == "boom"


def test_per_instance_overrides():
    """Module, code, and http_status can be overridden per instance."""
    err = DataSourceError(
        "custom", module="custom_mod", code="CUSTOM", http_status=418
    )
    assert err.module == "custom_mod"
    assert err.code == "CUSTOM"
    assert err.http_status == 418


def test_handler_returns_envelope_and_status():
    """A raised OilShieldError is rendered as the JSON envelope with its status."""
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/boom")
    def boom():
        raise ValidationError("value out of range")

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/boom")

    assert response.status_code == 400
    body = response.json()
    assert body == {
        "error": {
            "module": "scenario_simulator",
            "message": "value out of range",
            "code": "VALIDATION_ERROR",
        }
    }
