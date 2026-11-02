from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import (
    LocationNotFoundError,
    LocationPersistenceError,
    LocationSlugAlreadyExistsError,
)
from app.models.location import Location
from app.repositories.location import LocationRepository
from app.schemas.location import LocationCreate, LocationUpdate


def is_slug_conflict(error: IntegrityError) -> bool:
    diagnostic = getattr(error.orig, "diag", None)
    return getattr(diagnostic, "constraint_name", None) == "uq_locations_tenant_id_slug"


class LocationService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repository = LocationRepository(session)

    def create(
        self,
        tenant_id: UUID,
        payload: LocationCreate,
    ) -> Location:
        existing_location = self.repository.get_by_slug(
            tenant_id=tenant_id,
            slug=payload.slug,
        )

        if existing_location is not None:
            raise LocationSlugAlreadyExistsError(payload.slug)

        location = Location(
            tenant_id=tenant_id,
            name=payload.name,
            slug=payload.slug,
            timezone=payload.timezone,
            address_line_1=payload.address_line_1,
            address_line_2=payload.address_line_2,
            postal_code=payload.postal_code,
            city=payload.city,
            country_code=payload.country_code.upper(),
        )

        try:
            self.repository.add(location)
            self.session.commit()
        except IntegrityError as error:
            self.session.rollback()

            if is_slug_conflict(error):
                raise LocationSlugAlreadyExistsError(payload.slug) from error

            raise LocationPersistenceError() from error

        self.session.refresh(location)

        return location

    def get_by_id(
        self,
        tenant_id: UUID,
        location_id: UUID,
    ) -> Location:
        location = self.repository.get_by_id(
            tenant_id=tenant_id,
            location_id=location_id,
        )

        if location is None:
            raise LocationNotFoundError(location_id)

        return location

    def list_by_tenant(
        self,
        tenant_id: UUID,
        *,
        include_inactive: bool = False,
    ) -> list[Location]:
        return self.repository.list_by_tenant(
            tenant_id=tenant_id,
            include_inactive=include_inactive,
        )

    def update(
        self,
        tenant_id: UUID,
        location_id: UUID,
        payload: LocationUpdate,
    ) -> Location:
        location = self.get_by_id(
            tenant_id=tenant_id,
            location_id=location_id,
        )

        changes = payload.model_dump(exclude_unset=True)

        new_slug = changes.get("slug")

        if new_slug is not None and new_slug != location.slug:
            existing_location = self.repository.get_by_slug(
                tenant_id=tenant_id,
                slug=new_slug,
            )

            if existing_location is not None:
                raise LocationSlugAlreadyExistsError(new_slug)

        if "country_code" in changes:
            country_code = changes["country_code"]

            if country_code is not None:
                changes["country_code"] = country_code.upper()

        for field_name, value in changes.items():
            setattr(location, field_name, value)

        try:
            self.session.commit()
        except IntegrityError as error:
            self.session.rollback()

            if is_slug_conflict(error):
                raise LocationSlugAlreadyExistsError(location.slug) from error

            raise LocationPersistenceError() from error

        self.session.refresh(location)

        return location

    def deactivate(
        self,
        tenant_id: UUID,
        location_id: UUID,
    ) -> Location:
        location = self.get_by_id(
            tenant_id=tenant_id,
            location_id=location_id,
        )

        location.is_active = False

        try:
            self.session.commit()
        except IntegrityError as error:
            self.session.rollback()
            raise LocationPersistenceError() from error

        self.session.refresh(location)

        return location
