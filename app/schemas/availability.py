from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class AvailabilitySlotResponse(BaseModel):
    employee_id: UUID
    service_id: UUID
    starts_at: datetime
    ends_at: datetime
    duration_minutes: int
    buffer_before_minutes: int
    buffer_after_minutes: int
