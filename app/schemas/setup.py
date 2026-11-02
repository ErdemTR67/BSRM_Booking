from enum import Enum

from pydantic import BaseModel, Field


class SetupStepKey(str, Enum):
    LOCATION = "location"
    OPENING_HOURS = "opening_hours"
    SERVICE = "service"
    EMPLOYEE = "employee"
    EMPLOYEE_SERVICE = "employee_service"
    EMPLOYEE_AVAILABILITY = "employee_availability"


class SetupStepResponse(BaseModel):
    key: SetupStepKey
    complete: bool


class SetupStatusResponse(BaseModel):
    is_complete: bool
    progress_percent: int = Field(ge=0, le=100)
    next_step: SetupStepKey | None
    steps: list[SetupStepResponse]
