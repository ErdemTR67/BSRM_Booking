import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.employee import Employee
    from app.models.membership import Membership
    from app.models.platform_role import PlatformRole
    from app.models.refresh_token import RefreshToken
    from app.models.tenant_invitation import TenantInvitation


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    memberships: Mapped[list["Membership"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
    employees: Mapped[list["Employee"]] = relationship(back_populates="user")
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
    platform_role: Mapped["PlatformRole | None"] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
    accepted_invitations: Mapped[list["TenantInvitation"]] = relationship(
        foreign_keys="TenantInvitation.accepted_user_id",
        back_populates="accepted_user",
    )
    sent_invitations: Mapped[list["TenantInvitation"]] = relationship(
        foreign_keys="TenantInvitation.invited_by_user_id",
        back_populates="invited_by_user",
    )
