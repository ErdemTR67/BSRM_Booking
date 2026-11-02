from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import (
    LocationNotFoundError,
    ServiceNotFoundError,
    ServicePersistenceError,
)
from app.core.tenant_context import TenantContext
from app.models.service import Service
from app.repositories.location import LocationRepository
from app.repositories.service import ServiceRepository
from app.schemas.service import ServiceCreate, ServiceUpdate


class ServiceService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repository = ServiceRepository(session)
        self.location_repository = LocationRepository(session)

    def create(self, context: TenantContext, payload: ServiceCreate) -> Service:
        self._validate_optional_location(context.tenant_id, payload.location_id)
        service = Service(
            tenant_id=context.tenant_id,
            location_id=payload.location_id,
            name=payload.name,
            description=payload.description,
            duration_minutes=payload.duration_minutes,
            buffer_before_minutes=payload.buffer_before_minutes,
            buffer_after_minutes=payload.buffer_after_minutes,
            price_cents=payload.price_cents,
            currency=payload.currency,
            is_active=True,
        )

        try:
            self.repository.add(service)
            self.session.commit()
        except IntegrityError as error:
            self.session.rollback()
            raise ServicePersistenceError() from error

        self.session.refresh(service)
        return service

    def get_by_id(self, context: TenantContext, service_id: UUID) -> Service:
        service = self.repository.get_by_id(context.tenant_id, service_id)

        if service is None:
            raise ServiceNotFoundError(service_id)

        return service

    def list_by_tenant(
        self,
        context: TenantContext,
        *,
        is_active: bool | None = True,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Service], int]:
        return self.repository.list_by_tenant(
            context.tenant_id,
            is_active=is_active,
            page=page,
            page_size=page_size,
        )

    def update(
        self,
        context: TenantContext,
        service_id: UUID,
        payload: ServiceUpdate,
    ) -> Service:
        service = self.get_by_id(context, service_id)
        changes = payload.model_dump(exclude_unset=True)

        if "location_id" in changes:
            self._validate_optional_location(
                context.tenant_id,
                changes["location_id"],
            )

        for field_name, value in changes.items():
            setattr(service, field_name, value)

        self._commit(service)
        return service

    def deactivate(self, context: TenantContext, service_id: UUID) -> Service:
        service = self.get_by_id(context, service_id)
        service.is_active = False
        self._commit(service)
        return service

    def _validate_optional_location(
        self,
        tenant_id: UUID,
        location_id: UUID | None,
    ) -> None:
        if location_id is None:
            return

        location = self.location_repository.get_by_id(tenant_id, location_id)

        if location is None or not location.is_active:
            raise LocationNotFoundError(location_id)

    def _commit(self, service: Service) -> None:
        try:
            self.session.commit()
        except IntegrityError as error:
            self.session.rollback()
            raise ServicePersistenceError() from error

        self.session.refresh(service)
