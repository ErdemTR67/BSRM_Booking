from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.location import Location


class LocationRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(
        self,
        tenant_id: UUID,
        location_id: UUID,
    ) -> Location | None:
        statement = select(Location).where(
            Location.id == location_id,
            Location.tenant_id == tenant_id,
        )

        result = self.session.execute(statement)

        return result.scalar_one_or_none()

    def get_by_slug(
        self,
        tenant_id: UUID,
        slug: str,
    ) -> Location | None:
        statement = select(Location).where(
            Location.tenant_id == tenant_id,
            Location.slug == slug,
        )

        result = self.session.execute(statement)

        return result.scalar_one_or_none()

    def list_by_tenant(
        self,
        tenant_id: UUID,
        *,
        include_inactive: bool = False,
    ) -> list[Location]:
        statement = select(Location).where(
            Location.tenant_id == tenant_id,
        )

        if not include_inactive:
            statement = statement.where(
                Location.is_active.is_(True),
            )

        statement = statement.order_by(
            Location.name.asc(),
        )

        result = self.session.execute(statement)

        return list(result.scalars().all())

    def add(self, location: Location) -> Location:
        self.session.add(location)
        self.session.flush()

        return location