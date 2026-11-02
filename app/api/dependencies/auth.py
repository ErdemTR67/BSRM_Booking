from typing import Annotated

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.database import get_database_session, set_session_user
from app.core.exceptions import InvalidAccessTokenError
from app.core.tokens import AccessTokenError, decode_access_token
from app.models.user import User
from app.repositories.user import UserRepository


oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/login",
    auto_error=False,
)


def get_current_user(
    token: Annotated[str | None, Depends(oauth2_scheme)],
    session: Annotated[Session, Depends(get_database_session)],
) -> User:
    if token is None:
        raise InvalidAccessTokenError()

    try:
        user_id = decode_access_token(token)
    except AccessTokenError as error:
        raise InvalidAccessTokenError() from error

    user = UserRepository(session).get_by_id(user_id)

    if user is None or not user.is_active:
        raise InvalidAccessTokenError()

    set_session_user(session, user.id)
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
