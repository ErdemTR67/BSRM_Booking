from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.service import Service


class ServiceRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, tenant_id: UUID, service_id: UUID) -> Service | None:
        statement = select(Service).where(
            Service.id == service_id,
            Service.tenant_id == tenant_id,
        )
        return self.session.scalar(statement)

    def list_by_tenant(
        self,
        tenant_id: UUID,
        *,
        is_active: bool | None = True,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Service], int]:
        conditions = [Service.tenant_id == tenant_id]

        if is_active is not None:
            conditions.append(Service.is_active.is_(is_active))

        total = self.session.scalar(
            select(func.count()).select_from(Service).where(*conditions)
        ) or 0
        statement = (
            select(Service)
            .where(*conditions)
            .order_by(Service.name.asc(), Service.id.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(self.session.scalars(statement)), total

    def add(self, service: Service) -> Service:
        self.session.add(service)
        self.session.flush()
        return service
