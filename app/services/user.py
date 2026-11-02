from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import (
    UserEmailAlreadyExistsError,
    UserNotFoundError,
    UserPersistenceError,
)
from app.core.security import hash_password
from app.models.user import User
from app.repositories.user import UserRepository
from app.schemas.user import UserUpdate


class UserService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repository = UserRepository(session)

    def get_by_email(self, email: str) -> User:
        normalized_email = email.strip().lower()

        user = self.repository.get_by_email(
            email=normalized_email,
        )

        if user is None:
            raise UserNotFoundError()

        return user

    def get_by_id(self, user_id: UUID) -> User:
        user = self.repository.get_by_id(
            user_id=user_id,
        )

        if user is None:
            raise UserNotFoundError(user_id)

        return user

    def update(
        self,
        user_id: UUID,
        payload: UserUpdate,
    ) -> User:
        user = self.get_by_id(user_id)

        if payload.email is not None:
            normalized_email = str(payload.email).strip().lower()

            existing_user = self.repository.get_by_email(
                email=normalized_email,
            )

            if (
                existing_user is not None
                and existing_user.id != user.id
            ):
                raise UserEmailAlreadyExistsError(
                    normalized_email,
                )

            user.email = normalized_email

        if payload.first_name is not None:
            user.first_name = payload.first_name.strip()

        if payload.last_name is not None:
            user.last_name = payload.last_name.strip()

        if payload.password is not None:
            user.password_hash = hash_password(
                payload.password,
            )

        if payload.is_active is not None:
            user.is_active = payload.is_active

        try:
            self.session.commit()
        except IntegrityError as error:
            self.session.rollback()

            if payload.email is not None:
                normalized_email = (
                    str(payload.email).strip().lower()
                )

                raise UserEmailAlreadyExistsError(
                    normalized_email,
                ) from error

            raise UserPersistenceError() from error

        self.session.refresh(user)

        return user

    def deactivate(self, user_id: UUID) -> User:
        user = self.get_by_id(user_id)

        user.is_active = False

        try:
            self.session.commit()
        except IntegrityError as error:
            self.session.rollback()
            raise UserPersistenceError() from error

        self.session.refresh(user)

        return user
