from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.customer import Customer


class CustomerRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, tenant_id: UUID, customer_id: UUID) -> Customer | None:
        statement = select(Customer).where(
            Customer.id == customer_id,
            Customer.tenant_id == tenant_id,
        )
        return self.session.scalar(statement)

    def list_by_tenant(
        self,
        tenant_id: UUID,
        *,
        query: str | None = None,
        email: str | None = None,
        phone: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Customer], int]:
        conditions = [Customer.tenant_id == tenant_id]
        if query:
            pattern = f"%{query}%"
            conditions.append(
                or_(
                    Customer.first_name.ilike(pattern),
                    Customer.last_name.ilike(pattern),
                    Customer.email.ilike(pattern),
                    Customer.phone.ilike(pattern),
                )
            )
        if email:
            conditions.append(func.lower(Customer.email) == email.lower())
        if phone:
            conditions.append(Customer.phone == phone)
        total = self.session.scalar(
            select(func.count()).select_from(Customer).where(*conditions)
        ) or 0
        statement = (
            select(Customer)
            .where(*conditions)
            .order_by(Customer.last_name.asc(), Customer.first_name.asc(), Customer.id.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(self.session.scalars(statement)), total

    def add(self, customer: Customer) -> Customer:
        self.session.add(customer)
        self.session.flush()
        return customer

    def delete(self, customer: Customer) -> None:
        self.session.delete(customer)
