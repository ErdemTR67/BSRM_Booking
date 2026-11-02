from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.api.dependencies.auth import CurrentUser
from app.core.database import get_database_session
from app.core.exceptions import InsufficientPermissionsError
from app.models.platform_role import PlatformRole
from app.repositories.platform_role import PlatformRoleRepository


def get_current_platform_admin(
    current_user: CurrentUser,
    session: Annotated[Session, Depends(get_database_session)],
) -> PlatformRole:
    platform_role = PlatformRoleRepository(session).get_active_admin_by_user(
        current_user.id
    )
    if platform_role is None:
        raise InsufficientPermissionsError()
    return platform_role


CurrentPlatformAdmin = Annotated[
    PlatformRole,
    Depends(get_current_platform_admin),
]
