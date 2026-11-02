from urllib.parse import urlsplit
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.exceptions import (
    BookingSiteAlreadyExistsError,
    BookingSiteNotFoundError,
    BookingSitePersistenceError,
    LocationNotFoundError,
)
from app.core.tenant_context import TenantContext
from app.core.tokens import generate_booking_site_key, hash_booking_site_key
from app.models.booking_site import BookingSite
from app.repositories.booking_site import BookingSiteRepository
from app.repositories.location import LocationRepository
from app.schemas.booking_site import BookingSiteCreate, BookingSiteUpdate


class BookingSiteService:
    def __init__(self, session: Session, settings: Settings | None = None) -> None:
        self.session = session
        self.settings = settings or get_settings()
        self.repository = BookingSiteRepository(session)
        self.location_repository = LocationRepository(session)

    def create(
        self, context: TenantContext, payload: BookingSiteCreate
    ) -> tuple[BookingSite, str]:
        if self.repository.get_by_tenant(context.tenant_id) is not None:
            raise BookingSiteAlreadyExistsError()
        self._validate_location(context.tenant_id, payload.default_location_id)
        origins = self._normalize_origins(payload.allowed_origins)
        name = payload.name.strip()
        if not name:
            raise BookingSitePersistenceError("The booking site name cannot be blank.")
        raw_key = generate_booking_site_key(
            production=self.settings.app_environment == "production"
        )
        site = BookingSite(
            tenant_id=context.tenant_id,
            name=name,
            publishable_key_hash=hash_booking_site_key(raw_key),
            key_prefix=raw_key[:20],
            allowed_origins=origins,
            default_location_id=payload.default_location_id,
            slot_interval_minutes=payload.slot_interval_minutes,
            minimum_notice_minutes=payload.minimum_notice_minutes,
            maximum_advance_days=payload.maximum_advance_days,
            require_phone=payload.require_phone,
            booking_enabled=payload.booking_enabled,
        )
        try:
            self.repository.add(site)
            self.session.commit()
        except IntegrityError as error:
            self.session.rollback()
            raise BookingSitePersistenceError() from error
        return site, raw_key

    def get(self, context: TenantContext) -> BookingSite:
        site = self.repository.get_by_tenant(context.tenant_id)
        if site is None:
            raise BookingSiteNotFoundError()
        return site

    def update(
        self, context: TenantContext, payload: BookingSiteUpdate
    ) -> BookingSite:
        site = self.get(context)
        changes = payload.model_dump(exclude_unset=True)
        if "default_location_id" in changes:
            self._validate_location(context.tenant_id, changes["default_location_id"])
        if "allowed_origins" in changes:
            changes["allowed_origins"] = self._normalize_origins(changes["allowed_origins"])
        if "name" in changes:
            changes["name"] = changes["name"].strip()
            if not changes["name"]:
                raise BookingSitePersistenceError("The booking site name cannot be blank.")
        for field_name, value in changes.items():
            setattr(site, field_name, value)
        self._commit()
        return site

    def rotate_key(self, context: TenantContext) -> tuple[BookingSite, str]:
        site = self.get(context)
        raw_key = generate_booking_site_key(
            production=self.settings.app_environment == "production"
        )
        site.publishable_key_hash = hash_booking_site_key(raw_key)
        site.key_prefix = raw_key[:20]
        self._commit()
        return site, raw_key

    def deactivate(self, context: TenantContext) -> BookingSite:
        site = self.get(context)
        site.is_active = False
        site.booking_enabled = False
        self._commit()
        return site

    def _validate_location(self, tenant_id: UUID, location_id: UUID | None) -> None:
        if location_id is None:
            return
        location = self.location_repository.get_by_id(tenant_id, location_id)
        if location is None or not location.is_active:
            raise LocationNotFoundError(location_id)

    def _normalize_origins(self, origins: list[str]) -> list[str]:
        normalized: list[str] = []
        for origin in origins:
            parsed = urlsplit(origin.strip())
            if (
                parsed.scheme not in {"http", "https"}
                or parsed.hostname is None
                or parsed.username is not None
                or parsed.password is not None
                or parsed.path not in {"", "/"}
                or parsed.query
                or parsed.fragment
                or "*" in origin
            ):
                raise BookingSitePersistenceError("Each allowed origin must be an HTTP(S) origin without a path.")
            if self.settings.app_environment == "production" and parsed.scheme != "https":
                raise BookingSitePersistenceError("Allowed origins must use HTTPS in production.")
            try:
                port_number = parsed.port
            except ValueError as error:
                raise BookingSitePersistenceError("An allowed origin contains an invalid port.") from error
            host = parsed.hostname.lower()
            if ":" in host:
                host = f"[{host}]"
            port = f":{port_number}" if port_number is not None else ""
            item = f"{parsed.scheme.lower()}://{host}{port}"
            if item not in normalized:
                normalized.append(item)
        return normalized

    def _commit(self) -> None:
        try:
            self.session.commit()
        except IntegrityError as error:
            self.session.rollback()
            raise BookingSitePersistenceError() from error
