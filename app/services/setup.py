from datetime import date, time

from sqlalchemy.orm import Session

from app.core.tenant_context import TenantContext
from app.repositories.setup import ScheduleCandidate, SetupRepository
from app.schemas.setup import SetupStatusResponse, SetupStepKey, SetupStepResponse


class SetupService:
    STEP_ORDER = (
        SetupStepKey.LOCATION,
        SetupStepKey.OPENING_HOURS,
        SetupStepKey.SERVICE,
        SetupStepKey.EMPLOYEE,
        SetupStepKey.EMPLOYEE_SERVICE,
        SetupStepKey.EMPLOYEE_AVAILABILITY,
    )

    def __init__(self, session: Session) -> None:
        self.repository = SetupRepository(session)

    def get_status(
        self,
        context: TenantContext,
        *,
        today: date | None = None,
    ) -> SetupStatusResponse:
        reference_date = today or date.today()
        completion = {
            SetupStepKey.LOCATION: self.repository.has_active_location(context.tenant_id),
            SetupStepKey.OPENING_HOURS: self.repository.has_active_opening_hour(
                context.tenant_id
            ),
            SetupStepKey.SERVICE: self.repository.has_active_service(context.tenant_id),
            SetupStepKey.EMPLOYEE: self.repository.has_bookable_employee(context.tenant_id),
            SetupStepKey.EMPLOYEE_SERVICE: self.repository.has_active_employee_service(
                context.tenant_id
            ),
            SetupStepKey.EMPLOYEE_AVAILABILITY: self._has_usable_schedule(
                self.repository.list_schedule_candidates(
                    context.tenant_id,
                    today=reference_date,
                )
            ),
        }
        steps = [
            SetupStepResponse(key=key, complete=completion[key])
            for key in self.STEP_ORDER
        ]
        completed_count = sum(step.complete for step in steps)
        next_step = next((step.key for step in steps if not step.complete), None)
        return SetupStatusResponse(
            is_complete=completed_count == len(steps),
            progress_percent=round(completed_count * 100 / len(steps)),
            next_step=next_step,
            steps=steps,
        )

    @staticmethod
    def _has_usable_schedule(candidates: list[ScheduleCandidate]) -> bool:
        for candidate in candidates:
            starts_at = max(
                candidate.opening_starts_at,
                candidate.availability_starts_at,
            )
            ends_at = min(
                candidate.opening_ends_at,
                candidate.availability_ends_at,
            )
            available_minutes = SetupService._minutes(ends_at) - SetupService._minutes(
                starts_at
            )
            required_minutes = (
                candidate.buffer_before_minutes
                + candidate.duration_minutes
                + candidate.buffer_after_minutes
            )
            if available_minutes >= required_minutes:
                return True
        return False

    @staticmethod
    def _minutes(value: time) -> int:
        return value.hour * 60 + value.minute
