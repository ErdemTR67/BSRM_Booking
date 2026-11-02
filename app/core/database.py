from collections.abc import Generator
from uuid import UUID

from sqlalchemy import Connection, Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

_TENANT_CONTEXT_KEY = "rls_tenant_id"
_USER_CONTEXT_KEY = "rls_user_id"


def create_application_engine(database_url: str) -> Engine:
    settings = get_settings()
    application_engine = create_engine(database_url, pool_pre_ping=True)

    @event.listens_for(application_engine, "begin")
    def assume_application_role(connection: Connection) -> None:
        # The role name is constrained by Settings to a safe PostgreSQL identifier.
        connection.exec_driver_sql(
            f'SET LOCAL ROLE "{settings.database_application_role}"'
        )

    return application_engine


def _set_local_context(connection: Connection, setting: str, value: UUID) -> None:
    # UUID is serialized before interpolation; PostgreSQL SET does not accept a bind here.
    connection.exec_driver_sql(f"SET LOCAL {setting} = '{value}'")


@event.listens_for(Session, "after_begin")
def restore_rls_context(
    session: Session,
    transaction: object,
    connection: Connection,
) -> None:
    if getattr(transaction, "nested", False):
        return
    user_id = session.info.get(_USER_CONTEXT_KEY)
    tenant_id = session.info.get(_TENANT_CONTEXT_KEY)
    if isinstance(user_id, UUID):
        _set_local_context(connection, "app.user_id", user_id)
    if isinstance(tenant_id, UUID):
        _set_local_context(connection, "app.tenant_id", tenant_id)


def set_session_user(session: Session, user_id: UUID) -> None:
    session.info[_USER_CONTEXT_KEY] = user_id
    _set_local_context(session.connection(), "app.user_id", user_id)


def set_session_tenant(session: Session, tenant_id: UUID) -> None:
    session.info[_TENANT_CONTEXT_KEY] = tenant_id
    _set_local_context(session.connection(), "app.tenant_id", tenant_id)


settings = get_settings()
engine = create_application_engine(settings.database_url)

SessionLocal = sessionmaker(
    bind=engine,
    class_=Session,
    autoflush=False,
    expire_on_commit=False,
)


def get_database_session() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session
