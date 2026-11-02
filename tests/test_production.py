import logging

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.exc import OperationalError

from app.core.database import get_database_session
from app.core.config import Settings
from app.main import app, create_app


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "database_url": "postgresql+psycopg://user:password@database.invalid/booking",
        "jwt_secret_key": "a-strong-production-secret-with-40-characters",
        "app_environment": "production",
        "allowed_hosts": ["testserver"],
        "expose_api_docs": False,
        "invitation_frontend_url": "https://dashboard.example.com/accept-invitation",
        "email_delivery_mode": "smtp",
        "smtp_host": "smtp.example.com",
        "smtp_from_email": "booking@example.com",
        "public_booking_challenge_mode": "turnstile",
        "turnstile_secret_key": "turnstile-test-secret",
    }
    values.update(overrides)
    return Settings(**values)


def test_production_rejects_weak_jwt_secret() -> None:
    with pytest.raises(ValidationError, match="strong secret"):
        _settings(jwt_secret_key="change-me")


def test_production_rejects_wildcard_cors() -> None:
    with pytest.raises(ValidationError, match="Wildcard CORS"):
        _settings(cors_origins=["*"])


def test_production_requires_turnstile_for_public_booking() -> None:
    with pytest.raises(ValidationError, match="PUBLIC_BOOKING_CHALLENGE_MODE"):
        _settings(public_booking_challenge_mode="disabled")

    with pytest.raises(ValidationError, match="TURNSTILE_SECRET_KEY"):
        _settings(turnstile_secret_key=None)


def test_configured_cors_uses_explicit_origin() -> None:
    production_app = create_app(
        _settings(cors_origins=["https://dashboard.example.com/"])
    )
    with TestClient(production_app) as client:
        response = client.options(
            "/health",
            headers={
                "Origin": "https://dashboard.example.com",
                "Access-Control-Request-Method": "GET",
            },
        )

    assert response.status_code == status.HTTP_200_OK
    assert response.headers["access-control-allow-origin"] == "https://dashboard.example.com"
    assert response.headers["access-control-allow-credentials"] == "true"


def test_production_disables_api_documentation_and_adds_security_headers() -> None:
    production_app = create_app(_settings())
    with TestClient(production_app) as client:
        health = client.get("/health")
        docs = client.get("/docs")
        openapi = client.get("/openapi.json")

    assert health.status_code == status.HTTP_200_OK
    assert health.headers["strict-transport-security"].startswith("max-age=")
    assert health.headers["x-content-type-options"] == "nosniff"
    assert health.headers["x-frame-options"] == "DENY"
    assert docs.status_code == status.HTTP_404_NOT_FOUND
    assert openapi.status_code == status.HTTP_404_NOT_FOUND


def test_health_readiness_docs_and_request_id(client: TestClient) -> None:
    health = client.get("/health")
    ready = client.get("/ready")
    docs = client.get("/docs")

    assert health.status_code == status.HTTP_200_OK
    assert health.json() == {"status": "ok"}
    assert len(health.headers["X-Request-ID"]) == 32
    assert ready.status_code == status.HTTP_200_OK
    assert ready.json() == {"status": "ready"}
    assert docs.status_code == status.HTTP_200_OK
    assert "Swagger UI" in docs.text


def test_readiness_returns_503_when_database_is_unavailable(client: TestClient) -> None:
    class UnavailableSession:
        def execute(self, statement: object) -> None:
            raise OperationalError("SELECT 1", {}, Exception("database unavailable"))

    app.dependency_overrides[get_database_session] = lambda: UnavailableSession()
    try:
        response = client.get("/ready")
    finally:
        app.dependency_overrides.pop(get_database_session, None)

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert response.json()["error"]["code"] == "service_unavailable"


def test_request_logging_does_not_log_query_values(
    client: TestClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO)
    marker = "private-customer@example.com"
    response = client.get(f"/health?email={marker}")

    assert response.status_code == status.HTTP_200_OK
    assert marker not in caplog.text
