from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models.booking_site import BookingSite


class BookingSiteRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_tenant(self, tenant_id: UUID) -> BookingSite | None:
        return self.session.scalar(
            select(BookingSite).where(BookingSite.tenant_id == tenant_id)
        )

    def resolve_public_key(self, key_hash: str) -> BookingSite | None:
        statement = select(BookingSite).from_statement(
            text("SELECT * FROM public.app_resolve_booking_site(:key_hash)")
        )
        return self.session.scalar(statement, {"key_hash": key_hash})

    def add(self, booking_site: BookingSite) -> BookingSite:
        self.session.add(booking_site)
        self.session.flush()
        return booking_site
