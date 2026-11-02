from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import CustomerNotFoundError, CustomerPersistenceError
from app.core.tenant_context import TenantContext
from app.models.customer import Customer
from app.repositories.customer import CustomerRepository
from app.schemas.customer import CustomerCreate, CustomerUpdate


class CustomerService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repository = CustomerRepository(session)

    def create(self, context: TenantContext, payload: CustomerCreate) -> Customer:
        customer = Customer(
            tenant_id=context.tenant_id,
            first_name=payload.first_name,
            last_name=payload.last_name,
            email=self._normalize_email(payload.email),
            phone=payload.phone,
            notes=payload.notes,
            marketing_consent=payload.marketing_consent,
        )
        return self._save(customer, add=True)

    def get_by_id(self, context: TenantContext, customer_id: UUID) -> Customer:
        customer = self.repository.get_by_id(context.tenant_id, customer_id)
        if customer is None:
            raise CustomerNotFoundError(customer_id)
        return customer

    def list_by_tenant(
        self,
        context: TenantContext,
        *,
        query: str | None = None,
        email: str | None = None,
        phone: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Customer], int]:
        return self.repository.list_by_tenant(
            context.tenant_id,
            query=query.strip() if query else None,
            email=email.strip() if email else None,
            phone=phone.strip() if phone else None,
            page=page,
            page_size=page_size,
        )

    def update(
        self,
        context: TenantContext,
        customer_id: UUID,
        payload: CustomerUpdate,
    ) -> Customer:
        customer = self.get_by_id(context, customer_id)
        changes = payload.model_dump(exclude_unset=True)
        if changes.get("email") is not None:
            changes["email"] = self._normalize_email(changes["email"])
        for field_name, value in changes.items():
            setattr(customer, field_name, value)
        return self._save(customer)

    def delete(self, context: TenantContext, customer_id: UUID) -> None:
        customer = self.get_by_id(context, customer_id)
        try:
            self.repository.delete(customer)
            self.session.commit()
        except IntegrityError as error:
            self.session.rollback()
            raise CustomerPersistenceError() from error

    @staticmethod
    def _normalize_email(email: object | None) -> str | None:
        return str(email).lower() if email is not None else None

    def _save(self, customer: Customer, *, add: bool = False) -> Customer:
        try:
            if add:
                self.repository.add(customer)
            self.session.commit()
        except IntegrityError as error:
            self.session.rollback()
            raise CustomerPersistenceError() from error
        self.session.refresh(customer)
        return customer
