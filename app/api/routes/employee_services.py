from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies.tenant import HeaderTenantContext, require_header_roles
from app.core.database import get_database_session
from app.core.tenant_context import TenantContext
from app.models.membership import MembershipRole
from app.schemas.service import EmployeeServiceResponse, EmployeeServiceUpsert
from app.services.employee_service import EmployeeServiceService


router = APIRouter(
    prefix="/employees/{employee_id}/services",
    tags=["Employee services"],
)


def get_employee_service_service(
    session: Annotated[Session, Depends(get_database_session)],
) -> EmployeeServiceService:
    return EmployeeServiceService(session)


EmployeeServiceWriteContext = Annotated[
    TenantContext,
    Depends(
        require_header_roles(
            MembershipRole.OWNER,
            MembershipRole.ADMIN,
            MembershipRole.MANAGER,
        )
    ),
]


@router.put("/{service_id}", response_model=EmployeeServiceResponse)
def upsert_employee_service(
    employee_id: UUID,
    service_id: UUID,
    payload: EmployeeServiceUpsert,
    context: EmployeeServiceWriteContext,
    service: Annotated[
        EmployeeServiceService,
        Depends(get_employee_service_service),
    ],
) -> EmployeeServiceResponse:
    result = service.upsert(context, employee_id, service_id, payload)
    return EmployeeServiceResponse.model_validate(result)


@router.get("", response_model=list[EmployeeServiceResponse])
def list_employee_services(
    employee_id: UUID,
    context: HeaderTenantContext,
    service: Annotated[
        EmployeeServiceService,
        Depends(get_employee_service_service),
    ],
) -> list[EmployeeServiceResponse]:
    results = service.list_by_employee(context, employee_id)
    return [EmployeeServiceResponse.model_validate(item) for item in results]


@router.delete("/{service_id}", response_model=EmployeeServiceResponse)
def deactivate_employee_service(
    employee_id: UUID,
    service_id: UUID,
    context: EmployeeServiceWriteContext,
    service: Annotated[
        EmployeeServiceService,
        Depends(get_employee_service_service),
    ],
) -> EmployeeServiceResponse:
    result = service.deactivate(context, employee_id, service_id)
    return EmployeeServiceResponse.model_validate(result)
