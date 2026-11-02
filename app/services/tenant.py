from uuid import UUID, uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import (
    TenantAlreadyExistsError,
    TenantNotFoundError,
    TenantPersistenceError,
)
from app.models.tenant import Tenant
from app.repositories.tenant import TenantRepository
from app.schemas.tenant import TenantCreate, TenantUpdate


class TenantService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repository = TenantRepository(session)

    def create(self, payload: TenantCreate) -> Tenant:
        existing_tenant = self.repository.get_by_slug(payload.slug)

        if existing_tenant is not None:
            raise TenantAlreadyExistsError(payload.slug)

        tenant = Tenant(
            id=uuid4(),
            name=payload.name,
            slug=payload.slug,
        )

        try:
            tenant = self.repository.add(tenant)
            self.session.commit()
        except IntegrityError as error:
            self.session.rollback()
            raise TenantAlreadyExistsError(payload.slug) from error

        return tenant

    def get_by_id(self, tenant_id: UUID) -> Tenant:
        tenant = self.repository.get_by_id(tenant_id)

        if tenant is None:
            raise TenantNotFoundError(tenant_id)

        return tenant

    def list_for_user(self, user_id: UUID) -> list[Tenant]:
        return self.repository.list_active_for_user(user_id)

    def list_all(self) -> list[Tenant]:
        return self.repository.list_all()

    def update(
        self,
        tenant_id: UUID,
        payload: TenantUpdate,
    ) -> Tenant:
        tenant = self.get_by_id(tenant_id)

        changes = payload.model_dump(exclude_unset=True)

        for field, value in changes.items():
            setattr(tenant, field, value)

        try:
            self.session.commit()
        except IntegrityError as error:
            self.session.rollback()
            raise TenantPersistenceError() from error

        self.session.refresh(tenant)

        return tenant

    def deactivate(self, tenant_id: UUID) -> Tenant:
        tenant = self.get_by_id(tenant_id)
        tenant.is_active = False

        try:
            self.session.commit()
        except IntegrityError as error:
            self.session.rollback()
            raise TenantPersistenceError() from error

        self.session.refresh(tenant)

        self.session.refresh(tenant)
        return tenant
