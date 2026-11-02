from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies.tenant import HeaderTenantContext, require_header_roles
from app.core.database import get_database_session
from app.core.tenant_context import TenantContext
from app.models.membership import MembershipRole
from app.schemas.employee import EmployeeCreate, EmployeeResponse, EmployeeUpdate
from app.schemas.pagination import PageResponse
from app.services.employee import EmployeeService


router = APIRouter(prefix="/employees", tags=["Employees"])


def get_employee_service(
    session: Annotated[Session, Depends(get_database_session)],
) -> EmployeeService:
    return EmployeeService(session)


EmployeeWriteContext = Annotated[
    TenantContext,
    Depends(
        require_header_roles(
            MembershipRole.OWNER,
            MembershipRole.ADMIN,
            MembershipRole.MANAGER,
        )
    ),
]


@router.post(
    "",
    response_model=EmployeeResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_employee(
    payload: EmployeeCreate,
    context: EmployeeWriteContext,
    service: Annotated[EmployeeService, Depends(get_employee_service)],
) -> EmployeeResponse:
    employee = service.create(context, payload)
    return EmployeeResponse.model_validate(employee)


@router.get("", response_model=PageResponse[EmployeeResponse])
def list_employees(
    context: HeaderTenantContext,
    service: Annotated[EmployeeService, Depends(get_employee_service)],
    location_id: UUID | None = Query(default=None),
    is_active: bool | None = Query(default=True),
    is_bookable: bool | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PageResponse[EmployeeResponse]:
    employees, total = service.list_by_tenant(
        context,
        location_id=location_id,
        is_active=is_active,
        is_bookable=is_bookable,
        page=page,
        page_size=page_size,
    )
    return PageResponse(
        items=[EmployeeResponse.model_validate(employee) for employee in employees],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/{employee_id}", response_model=EmployeeResponse)
def get_employee(
    employee_id: UUID,
    context: HeaderTenantContext,
    service: Annotated[EmployeeService, Depends(get_employee_service)],
) -> EmployeeResponse:
    employee = service.get_by_id(context, employee_id)
    return EmployeeResponse.model_validate(employee)


@router.patch("/{employee_id}", response_model=EmployeeResponse)
def update_employee(
    employee_id: UUID,
    payload: EmployeeUpdate,
    context: EmployeeWriteContext,
    service: Annotated[EmployeeService, Depends(get_employee_service)],
) -> EmployeeResponse:
    employee = service.update(context, employee_id, payload)
    return EmployeeResponse.model_validate(employee)


@router.delete("/{employee_id}", response_model=EmployeeResponse)
def deactivate_employee(
    employee_id: UUID,
    context: EmployeeWriteContext,
    service: Annotated[EmployeeService, Depends(get_employee_service)],
) -> EmployeeResponse:
    employee = service.deactivate(context, employee_id)
    return EmployeeResponse.model_validate(employee)
