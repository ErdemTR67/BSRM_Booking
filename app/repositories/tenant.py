from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models.tenant import Tenant


class TenantRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, tenant_id: UUID) -> Tenant | None:
        statement = select(Tenant).where(Tenant.id == tenant_id)
        return self.session.scalar(statement)

    def get_by_slug(self, slug: str) -> Tenant | None:
        statement = select(Tenant).where(Tenant.slug == slug)
        return self.session.scalar(statement)

    def list_all(self) -> list[Tenant]:
        statement = select(Tenant).order_by(Tenant.created_at.desc())
        return list(self.session.scalars(statement))

    def list_active_for_user(self, user_id: UUID) -> list[Tenant]:
        statement = select(Tenant).from_statement(
            text("SELECT * FROM app_list_active_tenants(:user_id)")
        )
        return list(self.session.scalars(statement.params(user_id=user_id)))

    def add(self, tenant: Tenant) -> Tenant:
        self.session.add(tenant)
        self.session.flush()
        self.session.refresh(tenant)
        return tenant
