import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exceptions import (
    ApplicationError,
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    PersistenceError,
    ResourceNotFoundError,
    ServiceUnavailableError,
    TooManyRequestsError,
)


logger = logging.getLogger(__name__)


def error_content(
    *,
    code: str,
    message: str,
    details: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    error: dict[str, object] = {"code": code, "message": message}

    if details is not None:
        error["details"] = details

    return {"error": error}


async def application_error_handler(
    request: Request,
    error: ApplicationError,
) -> JSONResponse:
    headers: dict[str, str] | None = None

    if isinstance(error, TooManyRequestsError):
        status_code = status.HTTP_429_TOO_MANY_REQUESTS
        headers = {"Retry-After": str(error.retry_after)}
    elif isinstance(error, AuthenticationError):
        status_code = status.HTTP_401_UNAUTHORIZED
        headers = {"WWW-Authenticate": "Bearer"}
    elif isinstance(error, AuthorizationError):
        status_code = status.HTTP_403_FORBIDDEN
    elif isinstance(error, ResourceNotFoundError):
        status_code = status.HTTP_404_NOT_FOUND
    elif isinstance(error, ConflictError):
        status_code = status.HTTP_409_CONFLICT
    elif isinstance(error, PersistenceError):
        status_code = status.HTTP_400_BAD_REQUEST
    elif isinstance(error, ServiceUnavailableError):
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    else:
        status_code = status.HTTP_400_BAD_REQUEST

    logger.info(
        "Application error %s on %s %s",
        error.code,
        request.method,
        request.url.path,
    )

    return JSONResponse(
        status_code=status_code,
        content=error_content(code=error.code, message=str(error)),
        headers=headers,
    )


async def validation_error_handler(
    request: Request,
    error: RequestValidationError,
) -> JSONResponse:
    details = [
        {
            "location": list(item["loc"]),
            "message": item["msg"],
            "type": item["type"],
        }
        for item in error.errors()
    ]

    logger.info("Validation error on %s %s", request.method, request.url.path)

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content=error_content(
            code="validation_error",
            message="The request data is invalid.",
            details=details,
        ),
    )


async def http_error_handler(
    request: Request,
    error: StarletteHTTPException,
) -> JSONResponse:
    message = error.detail if isinstance(error.detail, str) else "The request failed."

    logger.info(
        "HTTP error %s on %s %s",
        error.status_code,
        request.method,
        request.url.path,
    )

    return JSONResponse(
        status_code=error.status_code,
        content=error_content(code="http_error", message=message),
        headers=error.headers,
    )


async def unexpected_error_handler(
    request: Request,
    error: Exception,
) -> JSONResponse:
    logger.error(
        "Unexpected error on %s %s (type=%s)",
        request.method,
        request.url.path,
        type(error).__name__,
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_content(
            code="internal_server_error",
            message="An unexpected error occurred.",
        ),
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ApplicationError, application_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_error_handler)
    app.add_exception_handler(Exception, unexpected_error_handler)
