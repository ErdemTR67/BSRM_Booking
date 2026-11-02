from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.location_closure import LocationClosure


class LocationClosureRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(
        self,
        tenant_id: UUID,
        location_id: UUID,
        closure_id: UUID,
    ) -> LocationClosure | None:
        statement = select(LocationClosure).where(
            LocationClosure.id == closure_id,
            LocationClosure.tenant_id == tenant_id,
            LocationClosure.location_id == location_id,
        )
        return self.session.scalar(statement)

    def list_by_location(
        self,
        tenant_id: UUID,
        location_id: UUID,
    ) -> list[LocationClosure]:
        statement = (
            select(LocationClosure)
            .where(
                LocationClosure.tenant_id == tenant_id,
                LocationClosure.location_id == location_id,
            )
            .order_by(LocationClosure.starts_at.asc())
        )
        return list(self.session.scalars(statement))

    def add(self, closure: LocationClosure) -> LocationClosure:
        self.session.add(closure)
        self.session.flush()
        return closure

    def delete(self, closure: LocationClosure) -> None:
        self.session.delete(closure)
