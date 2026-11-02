from datetime import datetime, time
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import (
    LocationClosureNotFoundError,
    LocationClosurePersistenceError,
    LocationNotFoundError,
    OpeningHourNotFoundError,
    OpeningHourPersistenceError,
)
from app.core.tenant_context import TenantContext
from app.models.location_closure import LocationClosure
from app.models.opening_hour import OpeningHour
from app.repositories.location import LocationRepository
from app.repositories.location_closure import LocationClosureRepository
from app.repositories.opening_hour import OpeningHourRepository
from app.schemas.hours import (
    LocationClosureCreate,
    LocationClosureUpdate,
    OpeningHourCreate,
    OpeningHourUpdate,
)


class OpeningHourService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repository = OpeningHourRepository(session)
        self.location_repository = LocationRepository(session)

    def create(
        self,
        context: TenantContext,
        location_id: UUID,
        payload: OpeningHourCreate,
    ) -> OpeningHour:
        self._validate_location(context.tenant_id, location_id)
        opening_hour = OpeningHour(
            tenant_id=context.tenant_id,
            location_id=location_id,
            weekday=payload.weekday,
            starts_at=payload.starts_at,
            ends_at=payload.ends_at,
            is_active=True,
        )
        return self._save(opening_hour, add=True)

    def get_by_id(
        self,
        context: TenantContext,
        location_id: UUID,
        opening_hour_id: UUID,
    ) -> OpeningHour:
        self._validate_location(context.tenant_id, location_id)
        opening_hour = self.repository.get_by_id(
            context.tenant_id,
            location_id,
            opening_hour_id,
        )
        if opening_hour is None:
            raise OpeningHourNotFoundError(opening_hour_id)
        return opening_hour

    def list_by_location(
        self,
        context: TenantContext,
        location_id: UUID,
        *,
        is_active: bool | None = True,
    ) -> list[OpeningHour]:
        self._validate_location(context.tenant_id, location_id)
        return self.repository.list_by_location(
            context.tenant_id,
            location_id,
            is_active=is_active,
        )

    def update(
        self,
        context: TenantContext,
        location_id: UUID,
        opening_hour_id: UUID,
        payload: OpeningHourUpdate,
    ) -> OpeningHour:
        opening_hour = self.get_by_id(context, location_id, opening_hour_id)
        changes = payload.model_dump(exclude_unset=True)
        starts_at = changes.get("starts_at", opening_hour.starts_at)
        ends_at = changes.get("ends_at", opening_hour.ends_at)
        self._validate_time_range(starts_at, ends_at)
        for field_name, value in changes.items():
            setattr(opening_hour, field_name, value)
        return self._save(opening_hour)

    def deactivate(
        self,
        context: TenantContext,
        location_id: UUID,
        opening_hour_id: UUID,
    ) -> OpeningHour:
        opening_hour = self.get_by_id(context, location_id, opening_hour_id)
        opening_hour.is_active = False
        return self._save(opening_hour)

    def _validate_location(self, tenant_id: UUID, location_id: UUID) -> None:
        location = self.location_repository.get_by_id(tenant_id, location_id)
        if location is None or not location.is_active:
            raise LocationNotFoundError(location_id)

    @staticmethod
    def _validate_time_range(starts_at: time, ends_at: time) -> None:
        if starts_at >= ends_at:
            raise OpeningHourPersistenceError("starts_at must be earlier than ends_at")

    def _save(self, opening_hour: OpeningHour, *, add: bool = False) -> OpeningHour:
        try:
            if add:
                self.repository.add(opening_hour)
            self.session.commit()
        except IntegrityError as error:
            self.session.rollback()
            raise OpeningHourPersistenceError() from error
        self.session.refresh(opening_hour)
        return opening_hour


class LocationClosureService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repository = LocationClosureRepository(session)
        self.location_repository = LocationRepository(session)

    def create(
        self,
        context: TenantContext,
        location_id: UUID,
        payload: LocationClosureCreate,
    ) -> LocationClosure:
        self._validate_location(context.tenant_id, location_id)
        closure = LocationClosure(
            tenant_id=context.tenant_id,
            location_id=location_id,
            starts_at=payload.starts_at,
            ends_at=payload.ends_at,
            reason=payload.reason,
        )
        return self._save(closure, add=True)

    def get_by_id(
        self,
        context: TenantContext,
        location_id: UUID,
        closure_id: UUID,
    ) -> LocationClosure:
        self._validate_location(context.tenant_id, location_id)
        closure = self.repository.get_by_id(
            context.tenant_id,
            location_id,
            closure_id,
        )
        if closure is None:
            raise LocationClosureNotFoundError(closure_id)
        return closure

    def list_by_location(
        self,
        context: TenantContext,
        location_id: UUID,
    ) -> list[LocationClosure]:
        self._validate_location(context.tenant_id, location_id)
        return self.repository.list_by_location(context.tenant_id, location_id)

    def update(
        self,
        context: TenantContext,
        location_id: UUID,
        closure_id: UUID,
        payload: LocationClosureUpdate,
    ) -> LocationClosure:
        closure = self.get_by_id(context, location_id, closure_id)
        changes = payload.model_dump(exclude_unset=True)
        starts_at = changes.get("starts_at", closure.starts_at)
        ends_at = changes.get("ends_at", closure.ends_at)
        self._validate_time_range(starts_at, ends_at)
        for field_name, value in changes.items():
            setattr(closure, field_name, value)
        return self._save(closure)

    def delete(
        self,
        context: TenantContext,
        location_id: UUID,
        closure_id: UUID,
    ) -> None:
        closure = self.get_by_id(context, location_id, closure_id)
        try:
            self.repository.delete(closure)
            self.session.commit()
        except IntegrityError as error:
            self.session.rollback()
            raise LocationClosurePersistenceError() from error

    def _validate_location(self, tenant_id: UUID, location_id: UUID) -> None:
        location = self.location_repository.get_by_id(tenant_id, location_id)
        if location is None or not location.is_active:
            raise LocationNotFoundError(location_id)

    @staticmethod
    def _validate_time_range(starts_at: datetime, ends_at: datetime) -> None:
        if starts_at >= ends_at:
            raise LocationClosurePersistenceError("starts_at must be earlier than ends_at")

    def _save(self, closure: LocationClosure, *, add: bool = False) -> LocationClosure:
        try:
            if add:
                self.repository.add(closure)
            self.session.commit()
        except IntegrityError as error:
            self.session.rollback()
            raise LocationClosurePersistenceError() from error
        self.session.refresh(closure)
        return closure
