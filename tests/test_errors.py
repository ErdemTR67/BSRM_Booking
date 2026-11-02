import logging

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from app.api.routes.customers import get_customer_service
from app.main import app

from test_customers import _setup_owner


class ExplodingCustomerService:
    def list_by_tenant(self, *args: object, **kwargs: object) -> list[object]:
        raise RuntimeError("postgresql://user:secret@example.invalid/database")


def test_unexpected_errors_do_not_expose_internal_details(
    client: TestClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    headers, _ = _setup_owner(
        client,
        email="generic-error@example.com",
        slug="generic-error-tenant",
    )
    app.dependency_overrides[get_customer_service] = lambda: ExplodingCustomerService()

    caplog.set_level(logging.ERROR)
    try:
        with TestClient(
            app,
            base_url="http://localhost",
            raise_server_exceptions=False,
        ) as safe_client:
            response = safe_client.get("/api/v1/customers", headers=headers)
    finally:
        app.dependency_overrides.pop(get_customer_service, None)

    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert response.json() == {
        "error": {
            "code": "internal_server_error",
            "message": "An unexpected error occurred.",
        }
    }
    assert "secret" not in response.text
    assert "postgresql" not in response.text
    assert "secret" not in caplog.text
    assert "postgresql" not in caplog.text
