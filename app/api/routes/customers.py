from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies.tenant import HeaderTenantContext, require_header_roles
from app.core.database import get_database_session
from app.core.tenant_context import TenantContext
from app.models.membership import MembershipRole
from app.schemas.customer import CustomerCreate, CustomerResponse, CustomerUpdate
from app.schemas.pagination import PageResponse
from app.services.customer import CustomerService


router = APIRouter(prefix="/customers", tags=["Customers"])


def get_customer_service(
    session: Annotated[Session, Depends(get_database_session)],
) -> CustomerService:
    return CustomerService(session)


CustomerWriteContext = Annotated[
    TenantContext,
    Depends(
        require_header_roles(
            MembershipRole.OWNER,
            MembershipRole.ADMIN,
            MembershipRole.MANAGER,
        )
    ),
]


@router.post("", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED)
def create_customer(
    payload: CustomerCreate,
    context: CustomerWriteContext,
    service: Annotated[CustomerService, Depends(get_customer_service)],
) -> CustomerResponse:
    return CustomerResponse.model_validate(service.create(context, payload))


@router.get("", response_model=PageResponse[CustomerResponse])
def list_customers(
    context: HeaderTenantContext,
    service: Annotated[CustomerService, Depends(get_customer_service)],
    query: str | None = Query(default=None, min_length=1),
    email: str | None = Query(default=None, min_length=1),
    phone: str | None = Query(default=None, min_length=1),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PageResponse[CustomerResponse]:
    customers, total = service.list_by_tenant(
        context,
        query=query,
        email=email,
        phone=phone,
        page=page,
        page_size=page_size,
    )
    return PageResponse(
        items=[CustomerResponse.model_validate(item) for item in customers],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/{customer_id}", response_model=CustomerResponse)
def get_customer(
    customer_id: UUID,
    context: HeaderTenantContext,
    service: Annotated[CustomerService, Depends(get_customer_service)],
) -> CustomerResponse:
    return CustomerResponse.model_validate(service.get_by_id(context, customer_id))


@router.patch("/{customer_id}", response_model=CustomerResponse)
def update_customer(
    customer_id: UUID,
    payload: CustomerUpdate,
    context: CustomerWriteContext,
    service: Annotated[CustomerService, Depends(get_customer_service)],
) -> CustomerResponse:
    return CustomerResponse.model_validate(service.update(context, customer_id, payload))


@router.delete("/{customer_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_customer(
    customer_id: UUID,
    context: CustomerWriteContext,
    service: Annotated[CustomerService, Depends(get_customer_service)],
) -> Response:
    service.delete(context, customer_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
