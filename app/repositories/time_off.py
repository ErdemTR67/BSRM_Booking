from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.time_off import TimeOff, TimeOffStatus


class TimeOffRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(
        self,
        tenant_id: UUID,
        employee_id: UUID,
        time_off_id: UUID,
    ) -> TimeOff | None:
        statement = select(TimeOff).where(
            TimeOff.id == time_off_id,
            TimeOff.tenant_id == tenant_id,
            TimeOff.employee_id == employee_id,
        )
        return self.session.scalar(statement)

    def list_by_employee(
        self,
        tenant_id: UUID,
        employee_id: UUID,
        *,
        status: TimeOffStatus | None = None,
    ) -> list[TimeOff]:
        statement = select(TimeOff).where(
            TimeOff.tenant_id == tenant_id,
            TimeOff.employee_id == employee_id,
        )
        if status is not None:
            statement = statement.where(TimeOff.status == status.value)
        statement = statement.order_by(TimeOff.starts_at.asc())
        return list(self.session.scalars(statement))

    def add(self, time_off: TimeOff) -> TimeOff:
        self.session.add(time_off)
        self.session.flush()
        return time_off
