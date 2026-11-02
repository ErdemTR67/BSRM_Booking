from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies.tenant import HeaderTenantContext
from app.core.database import get_database_session
from app.schemas.availability import AvailabilitySlotResponse
from app.services.availability import AvailabilityService


router = APIRouter(prefix="/availability", tags=["Availability"])


def get_availability_service(
    session: Annotated[Session, Depends(get_database_session)],
) -> AvailabilityService:
    return AvailabilityService(session)


@router.get("", response_model=list[AvailabilitySlotResponse])
def get_availability(
    context: HeaderTenantContext,
    service: Annotated[AvailabilityService, Depends(get_availability_service)],
    location_id: UUID,
    service_id: UUID,
    date_: date = Query(alias="date"),
    employee_id: UUID | None = None,
    slot_interval_minutes: int = Query(default=15, ge=1, le=1440),
) -> list[AvailabilitySlotResponse]:
    return service.calculate(
        context,
        location_id=location_id,
        employee_id=employee_id,
        service_id=service_id,
        target_date=date_,
        slot_interval_minutes=slot_interval_minutes,
    )
