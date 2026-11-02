from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.platform_role import PlatformRole, PlatformRoleName


class PlatformRoleRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_active_admin_by_user(self, user_id: UUID) -> PlatformRole | None:
        statement = select(PlatformRole).where(
            PlatformRole.user_id == user_id,
            PlatformRole.role == PlatformRoleName.PLATFORM_ADMIN.value,
            PlatformRole.is_active.is_(True),
        )
        return self.session.scalar(statement)

    def add(self, platform_role: PlatformRole) -> PlatformRole:
        self.session.add(platform_role)
        self.session.flush()
        return platform_role
