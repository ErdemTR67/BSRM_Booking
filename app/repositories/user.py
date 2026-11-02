from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User


class UserRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(
        self,
        user_id: UUID,
    ) -> User | None:
        statement = select(User).where(
            User.id == user_id,
        )

        result = self.session.execute(statement)

        return result.scalar_one_or_none()

    def get_by_email(
        self,
        email: str,
    ) -> User | None:
        statement = select(User).where(
            User.email == email,
        )

        result = self.session.execute(statement)

        return result.scalar_one_or_none()

    def list_all(
        self,
        *,
        include_inactive: bool = False,
    ) -> list[User]:
        statement = select(User)

        if not include_inactive:
            statement = statement.where(
                User.is_active.is_(True),
            )

        statement = statement.order_by(
            User.email.asc(),
        )

        result = self.session.execute(statement)

        return list(result.scalars().all())

    def add(
        self,
        user: User,
    ) -> User:
        self.session.add(user)
        self.session.flush()

        return user