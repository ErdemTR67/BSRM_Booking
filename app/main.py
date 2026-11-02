# Copyright (c) 2026 Erdem Topcu. All rights reserved.
import logging
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.exception_handlers import register_exception_handlers
from app.api.routes.auth import router as auth_router
from app.api.routes.health import router as health_router
from app.api.routes.employees import router as employees_router
from app.api.routes.employee_services import router as employee_services_router
from app.api.routes.locations import router as locations_router
from app.api.routes.platform import router as platform_router
from app.api.routes.hours import router as hours_router
from app.api.routes.employee_availability import router as employee_availability_router
from app.api.routes.customers import router as customers_router
from app.api.routes.availability import router as availability_router
from app.api.routes.booking_site import router as booking_site_router
from app.api.routes.appointments import router as appointments_router
from app.api.routes.services import router as services_router
from app.api.routes.public_booking import router as public_booking_router
from app.api.routes.setup import router as setup_router
from app.api.routes.tenants import router as tenants_router
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging, reset_request_id, set_request_id


logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    active_settings = settings or get_settings()
    configure_logging(debug=active_settings.app_debug)
    application = FastAPI(
        title=active_settings.app_name,
        version="0.1.0",
        debug=active_settings.app_debug,
        docs_url="/docs" if active_settings.expose_api_docs else None,
        redoc_url="/redoc" if active_settings.expose_api_docs else None,
        openapi_url="/openapi.json" if active_settings.expose_api_docs else None,
    )

    if active_settings.cors_origins:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=active_settings.cors_origins,
            allow_credentials="*" not in active_settings.cors_origins,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    register_exception_handlers(application)

    @application.middleware("http")
    async def request_logging(request: Request, call_next):  # type: ignore[no-untyped-def]
        request_id = uuid4().hex
        request_id_token = set_request_id(request_id)
        started_at = perf_counter()
        try:
            if (
                request.method == "POST"
                and request.url.path == "/api/v1/public/booking/appointments"
                and request.headers.get("content-length")
            ):
                try:
                    content_length = int(request.headers["content-length"])
                except ValueError:
                    content_length = active_settings.public_booking_max_body_bytes + 1
                if content_length > active_settings.public_booking_max_body_bytes:
                    response = JSONResponse(
                        status_code=413,
                        content={
                            "error": {
                                "code": "request_too_large",
                                "message": "The request body is too large.",
                            }
                        },
                    )
                    response.headers["Cache-Control"] = "no-store"
                    if request.headers.get("origin"):
                        response.headers["Access-Control-Allow-Origin"] = request.headers["origin"]
                        response.headers["Vary"] = "Origin"
                    response.headers["X-Request-ID"] = request_id
                    response.headers["X-Content-Type-Options"] = "nosniff"
                    response.headers["X-Frame-Options"] = "DENY"
                    response.headers["Referrer-Policy"] = "no-referrer"
                    response.headers["Permissions-Policy"] = (
                        "camera=(), microphone=(), geolocation=()"
                    )
                    if active_settings.app_environment == "production":
                        response.headers["Strict-Transport-Security"] = (
                            "max-age=31536000; includeSubDomains"
                        )
                    logger.info(
                        "Request completed method=%s path=%s status=%s duration_ms=%.2f",
                        request.method,
                        request.url.path,
                        response.status_code,
                        (perf_counter() - started_at) * 1000,
                    )
                    return response
            if (
                request.method == "OPTIONS"
                and request.url.path.startswith("/api/v1/public/booking")
                and request.headers.get("origin")
            ):
                response = Response(status_code=204)
                response.headers["Access-Control-Allow-Origin"] = request.headers["origin"]
                response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
                response.headers["Access-Control-Allow-Headers"] = (
                    "Content-Type, X-BSRM-Site-Key, X-Booking-Challenge, Idempotency-Key"
                )
                response.headers["Access-Control-Max-Age"] = "600"
                response.headers["Vary"] = "Origin"
            else:
                response = await call_next(request)
            public_origin = getattr(request.state, "public_booking_origin", None)
            if public_origin:
                response.headers["Access-Control-Allow-Origin"] = public_origin
                response.headers["Vary"] = "Origin"
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["Referrer-Policy"] = "no-referrer"
            response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
            if request.url.path.startswith("/api/v1/auth"):
                response.headers["Cache-Control"] = "no-store"
            if request.url.path.startswith("/api/v1/public/booking"):
                response.headers["Cache-Control"] = "no-store"
            if active_settings.app_environment == "production":
                response.headers["Strict-Transport-Security"] = (
                    "max-age=31536000; includeSubDomains"
                )
            logger.info(
                "Request completed method=%s path=%s status=%s duration_ms=%.2f",
                request.method,
                request.url.path,
                response.status_code,
                (perf_counter() - started_at) * 1000,
            )
            return response
        finally:
            reset_request_id(request_id_token)

    # Added after the function middleware so Host validation remains the outermost layer.
    application.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=active_settings.allowed_hosts,
    )

    application.include_router(health_router)
    application.include_router(auth_router, prefix="/api/v1")
    application.include_router(platform_router, prefix="/api/v1")
    application.include_router(tenants_router, prefix="/api/v1")
    application.include_router(setup_router, prefix="/api/v1")
    application.include_router(locations_router, prefix="/api/v1")
    application.include_router(hours_router, prefix="/api/v1")
    application.include_router(employee_availability_router, prefix="/api/v1")
    application.include_router(customers_router, prefix="/api/v1")
    application.include_router(availability_router, prefix="/api/v1")
    application.include_router(booking_site_router, prefix="/api/v1")
    application.include_router(public_booking_router, prefix="/api/v1")
    application.include_router(appointments_router, prefix="/api/v1")
    application.include_router(employees_router, prefix="/api/v1")
    application.include_router(services_router, prefix="/api/v1")
    application.include_router(employee_services_router, prefix="/api/v1")
    return application


app = create_app()
