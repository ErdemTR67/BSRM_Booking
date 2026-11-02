from collections import defaultdict
from datetime import date, datetime, time, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.orm import Session

from app.core.exceptions import (
    AvailabilityCalculationError,
    EmployeeNotFoundError,
    LocationNotFoundError,
    ServiceNotFoundError,
)
from app.core.tenant_context import PublicBookingContext, TenantContext
from app.models.appointment import Appointment
from app.models.employee_availability import EmployeeAvailability
from app.models.time_off import TimeOff
from app.repositories.availability import AvailabilityRepository
from app.repositories.employee import EmployeeRepository
from app.repositories.location import LocationRepository
from app.repositories.service import ServiceRepository
from app.schemas.availability import AvailabilitySlotResponse


class AvailabilityService:
    def __init__(self, session: Session) -> None:
        self.repository = AvailabilityRepository(session)
        self.location_repository = LocationRepository(session)
        self.employee_repository = EmployeeRepository(session)
        self.service_repository = ServiceRepository(session)

    def calculate(
        self,
        context: TenantContext | PublicBookingContext,
        *,
        location_id: UUID,
        service_id: UUID,
        target_date: date,
        employee_id: UUID | None = None,
        slot_interval_minutes: int = 15,
    ) -> list[AvailabilitySlotResponse]:
        location = self.location_repository.get_by_id(context.tenant_id, location_id)
        if location is None or not location.is_active:
            raise LocationNotFoundError(location_id)
        service = self.service_repository.get_by_id(context.tenant_id, service_id)
        if (
            service is None
            or not service.is_active
            or (service.location_id is not None and service.location_id != location_id)
        ):
            raise ServiceNotFoundError(service_id)
        if employee_id is not None:
            employee = self.employee_repository.get_by_id(context.tenant_id, employee_id)
            if employee is None or employee.location_id != location_id:
                raise EmployeeNotFoundError(employee_id)

        try:
            timezone = ZoneInfo(location.timezone)
        except ZoneInfoNotFoundError as error:
            raise AvailabilityCalculationError("Location timezone is invalid.") from error

        day_start = datetime.combine(target_date, time.min, timezone)
        day_end = day_start + timedelta(days=1)
        weekday = target_date.weekday()
        eligible = self.repository.list_eligible_employees(
            context.tenant_id,
            location_id,
            service_id,
            employee_id=employee_id,
        )
        if not eligible:
            return []

        employee_ids = [employee.id for employee, _ in eligible]
        opening_hours = self.repository.list_opening_hours(
            context.tenant_id, location_id, weekday
        )
        if not opening_hours:
            return []
        closures = self.repository.list_closures(
            context.tenant_id, location_id, day_start, day_end
        )
        availabilities = self.repository.list_employee_availabilities(
            context.tenant_id, employee_ids, weekday, target_date
        )
        time_off = self.repository.list_approved_time_off(
            context.tenant_id, employee_ids, day_start, day_end
        )
        appointments = self.repository.list_active_appointments(
            context.tenant_id, employee_ids, day_start, day_end
        )

        openings = [
            self._local_interval(target_date, item.starts_at, item.ends_at, timezone)
            for item in opening_hours
        ]
        availability_by_employee = self._group_intervals(
            availabilities, target_date, timezone
        )
        blocks_by_employee = self._group_blocks(time_off, appointments)
        closure_blocks = [(item.starts_at, item.ends_at) for item in closures]

        slots: list[AvailabilitySlotResponse] = []
        seen: set[tuple[UUID, datetime]] = set()
        for employee, association in eligible:
            duration = association.custom_duration_minutes or service.duration_minutes
            total_minutes = (
                service.buffer_before_minutes + duration + service.buffer_after_minutes
            )
            for opening_start, opening_end in openings:
                for available_start, available_end in availability_by_employee[employee.id]:
                    allowed_start = max(opening_start, available_start)
                    allowed_end = min(opening_end, available_end)
                    candidate = self._ceil_to_grid(
                        allowed_start, day_start, slot_interval_minutes
                    )
                    while candidate + timedelta(minutes=total_minutes) <= allowed_end:
                        occupied_end = candidate + timedelta(minutes=total_minutes)
                        key = (employee.id, candidate)
                        blocked = self._overlaps_any(
                            candidate, occupied_end, closure_blocks
                        ) or self._overlaps_any(
                            candidate,
                            occupied_end,
                            blocks_by_employee[employee.id],
                        )
                        if not blocked and key not in seen:
                            slots.append(
                                AvailabilitySlotResponse(
                                    employee_id=employee.id,
                                    service_id=service.id,
                                    starts_at=candidate,
                                    ends_at=occupied_end,
                                    duration_minutes=duration,
                                    buffer_before_minutes=service.buffer_before_minutes,
                                    buffer_after_minutes=service.buffer_after_minutes,
                                )
                            )
                            seen.add(key)
                        candidate += timedelta(minutes=slot_interval_minutes)
        return sorted(slots, key=lambda item: (item.starts_at, str(item.employee_id)))

    def is_employee_interval_available(
        self,
        context: TenantContext | PublicBookingContext,
        *,
        location_id: UUID,
        employee_id: UUID,
        starts_at: datetime,
        ends_at: datetime,
    ) -> bool:
        location = self.location_repository.get_by_id(context.tenant_id, location_id)
        if location is None or not location.is_active:
            raise LocationNotFoundError(location_id)
        employee = self.employee_repository.get_by_id(context.tenant_id, employee_id)
        if (
            employee is None
            or employee.location_id != location_id
            or not employee.is_active
            or not employee.is_bookable
        ):
            raise EmployeeNotFoundError(employee_id)
        try:
            timezone = ZoneInfo(location.timezone)
        except ZoneInfoNotFoundError as error:
            raise AvailabilityCalculationError("Location timezone is invalid.") from error
        local_start = starts_at.astimezone(timezone)
        local_end = ends_at.astimezone(timezone)
        if local_start.date() != local_end.date() or local_start >= local_end:
            return False
        target_date = local_start.date()
        weekday = target_date.weekday()
        day_start = datetime.combine(target_date, time.min, timezone)
        day_end = day_start + timedelta(days=1)
        openings = [
            self._local_interval(target_date, item.starts_at, item.ends_at, timezone)
            for item in self.repository.list_opening_hours(
                context.tenant_id, location_id, weekday
            )
        ]
        availabilities = [
            self._local_interval(target_date, item.starts_at, item.ends_at, timezone)
            for item in self.repository.list_employee_availabilities(
                context.tenant_id, [employee_id], weekday, target_date
            )
        ]
        if not any(local_start >= start and local_end <= end for start, end in openings):
            return False
        if not any(
            local_start >= start and local_end <= end for start, end in availabilities
        ):
            return False
        closures = self.repository.list_closures(
            context.tenant_id, location_id, day_start, day_end
        )
        time_off = self.repository.list_approved_time_off(
            context.tenant_id, [employee_id], day_start, day_end
        )
        appointments = self.repository.list_active_appointments(
            context.tenant_id, [employee_id], day_start, day_end
        )
        blocks = [(item.starts_at, item.ends_at) for item in [*closures, *time_off, *appointments]]
        return not self._overlaps_any(local_start, local_end, blocks)

    @staticmethod
    def _local_interval(
        target_date: date,
        starts_at: time,
        ends_at: time,
        timezone: ZoneInfo,
    ) -> tuple[datetime, datetime]:
        return (
            datetime.combine(target_date, starts_at, timezone),
            datetime.combine(target_date, ends_at, timezone),
        )

    def _group_intervals(
        self,
        items: list[EmployeeAvailability],
        target_date: date,
        timezone: ZoneInfo,
    ) -> defaultdict[UUID, list[tuple[datetime, datetime]]]:
        grouped: defaultdict[UUID, list[tuple[datetime, datetime]]] = defaultdict(list)
        for item in items:
            grouped[item.employee_id].append(
                self._local_interval(target_date, item.starts_at, item.ends_at, timezone)
            )
        return grouped

    @staticmethod
    def _group_blocks(
        time_off: list[TimeOff],
        appointments: list[Appointment],
    ) -> defaultdict[UUID, list[tuple[datetime, datetime]]]:
        grouped: defaultdict[UUID, list[tuple[datetime, datetime]]] = defaultdict(list)
        for item in [*time_off, *appointments]:
            grouped[item.employee_id].append((item.starts_at, item.ends_at))
        return grouped

    @staticmethod
    def _ceil_to_grid(
        value: datetime,
        day_start: datetime,
        interval_minutes: int,
    ) -> datetime:
        elapsed_minutes = int((value - day_start).total_seconds() // 60)
        remainder = elapsed_minutes % interval_minutes
        if remainder:
            elapsed_minutes += interval_minutes - remainder
        return day_start + timedelta(minutes=elapsed_minutes)

    @staticmethod
    def _overlaps_any(
        starts_at: datetime,
        ends_at: datetime,
        blocks: list[tuple[datetime, datetime]],
    ) -> bool:
        return any(starts_at < block_end and ends_at > block_start for block_start, block_end in blocks)
