from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.dependencies.tenant import require_header_roles
from app.core.database import get_database_session
from app.core.tenant_context import TenantContext
from app.models.membership import MembershipRole
from app.schemas.booking_site import (
    BookingSiteCreate,
    BookingSiteIssuedResponse,
    BookingSiteResponse,
    BookingSiteUpdate,
)
from app.services.booking_site import BookingSiteService


router = APIRouter(prefix="/booking-site", tags=["Booking site"])


def get_booking_site_service(
    session: Annotated[Session, Depends(get_database_session)],
) -> BookingSiteService:
    return BookingSiteService(session)


BookingSiteWriteContext = Annotated[
    TenantContext,
    Depends(require_header_roles(MembershipRole.OWNER, MembershipRole.ADMIN)),
]


def _issued(site: object, raw_key: str) -> BookingSiteIssuedResponse:
    data = BookingSiteResponse.model_validate(site).model_dump()
    return BookingSiteIssuedResponse(**data, publishable_key=raw_key)


@router.post("", response_model=BookingSiteIssuedResponse, status_code=status.HTTP_201_CREATED)
def create_booking_site(
    payload: BookingSiteCreate,
    context: BookingSiteWriteContext,
    service: Annotated[BookingSiteService, Depends(get_booking_site_service)],
) -> BookingSiteIssuedResponse:
    site, raw_key = service.create(context, payload)
    return _issued(site, raw_key)


@router.get("", response_model=BookingSiteResponse)
def get_booking_site(
    context: BookingSiteWriteContext,
    service: Annotated[BookingSiteService, Depends(get_booking_site_service)],
) -> BookingSiteResponse:
    return BookingSiteResponse.model_validate(service.get(context))


@router.patch("", response_model=BookingSiteResponse)
def update_booking_site(
    payload: BookingSiteUpdate,
    context: BookingSiteWriteContext,
    service: Annotated[BookingSiteService, Depends(get_booking_site_service)],
) -> BookingSiteResponse:
    return BookingSiteResponse.model_validate(service.update(context, payload))


@router.post("/rotate-key", response_model=BookingSiteIssuedResponse)
def rotate_booking_site_key(
    context: BookingSiteWriteContext,
    service: Annotated[BookingSiteService, Depends(get_booking_site_service)],
) -> BookingSiteIssuedResponse:
    site, raw_key = service.rotate_key(context)
    return _issued(site, raw_key)


@router.delete("", response_model=BookingSiteResponse)
def deactivate_booking_site(
    context: BookingSiteWriteContext,
    service: Annotated[BookingSiteService, Depends(get_booking_site_service)],
) -> BookingSiteResponse:
    return BookingSiteResponse.model_validate(service.deactivate(context))
