from typing import Annotated

from fastapi import Depends, Header, Request
from sqlalchemy.orm import Session

from app.core.database import get_database_session, set_session_tenant
from app.core.exceptions import BookingSiteNotFoundError, PublicBookingOriginError
from app.core.tenant_context import PublicBookingContext
from app.core.tokens import hash_booking_site_key
from app.repositories.booking_site import BookingSiteRepository


def get_public_booking_context(
    request: Request,
    session: Annotated[Session, Depends(get_database_session)],
    site_key: Annotated[str | None, Header(alias="X-BSRM-Site-Key")] = None,
) -> PublicBookingContext:
    origin = request.headers.get("origin")
    normalized_origin = origin.rstrip("/") if origin else None
    request.state.public_booking_origin = normalized_origin
    if not site_key or not site_key.startswith(("bsrm_pk_live_", "bsrm_pk_test_")):
        raise BookingSiteNotFoundError()
    site = BookingSiteRepository(session).resolve_public_key(hash_booking_site_key(site_key))
    if site is None:
        raise BookingSiteNotFoundError()

    if normalized_origin is not None and normalized_origin not in site.allowed_origins:
        raise PublicBookingOriginError()

    set_session_tenant(session, site.tenant_id)
    return PublicBookingContext(
        tenant_id=site.tenant_id,
        booking_site_id=site.id,
        origin=normalized_origin,
        allowed_origins=tuple(site.allowed_origins),
        default_location_id=site.default_location_id,
        slot_interval_minutes=site.slot_interval_minutes,
        minimum_notice_minutes=site.minimum_notice_minutes,
        maximum_advance_days=site.maximum_advance_days,
        require_phone=site.require_phone,
    )


CurrentPublicBookingContext = Annotated[
    PublicBookingContext, Depends(get_public_booking_context)
]
