from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.opening_hour import OpeningHour


class OpeningHourRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(
        self,
        tenant_id: UUID,
        location_id: UUID,
        opening_hour_id: UUID,
    ) -> OpeningHour | None:
        statement = select(OpeningHour).where(
            OpeningHour.id == opening_hour_id,
            OpeningHour.tenant_id == tenant_id,
            OpeningHour.location_id == location_id,
        )
        return self.session.scalar(statement)

    def list_by_location(
        self,
        tenant_id: UUID,
        location_id: UUID,
        *,
        is_active: bool | None = True,
    ) -> list[OpeningHour]:
        statement = select(OpeningHour).where(
            OpeningHour.tenant_id == tenant_id,
            OpeningHour.location_id == location_id,
        )
        if is_active is not None:
            statement = statement.where(OpeningHour.is_active.is_(is_active))
        statement = statement.order_by(
            OpeningHour.weekday.asc(),
            OpeningHour.starts_at.asc(),
            OpeningHour.ends_at.asc(),
        )
        return list(self.session.scalars(statement))

    def add(self, opening_hour: OpeningHour) -> OpeningHour:
        self.session.add(opening_hour)
        self.session.flush()
        return opening_hour
