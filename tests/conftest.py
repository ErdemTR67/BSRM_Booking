import os
from collections.abc import Generator

import psycopg
import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from psycopg import sql
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_database_session
from app.main import app


@pytest.fixture(scope="session")
def test_database_url() -> Generator[str, None, None]:
    source_url = make_url(get_settings().database_url)
    database_name = f"{source_url.database}_test"
    test_url = source_url.set(database=database_name)
    admin_url = source_url.set(drivername="postgresql", database="postgres")

    with psycopg.connect(admin_url.render_as_string(hide_password=False), autocommit=True) as connection:
        exists = connection.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s", (database_name,)
        ).fetchone()
        if exists is None:
            connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database_name)))

    previous_url = os.environ.get("DATABASE_URL")
    previous_migration_url = os.environ.get("DATABASE_MIGRATION_URL")
    os.environ["DATABASE_URL"] = test_url.render_as_string(hide_password=False)
    os.environ["DATABASE_MIGRATION_URL"] = test_url.render_as_string(hide_password=False)
    get_settings.cache_clear()
    command.upgrade(Config("alembic.ini"), "head")

    yield os.environ["DATABASE_URL"]

    if previous_url is None:
        os.environ.pop("DATABASE_URL", None)
    else:
        os.environ["DATABASE_URL"] = previous_url
    if previous_migration_url is None:
        os.environ.pop("DATABASE_MIGRATION_URL", None)
    else:
        os.environ["DATABASE_MIGRATION_URL"] = previous_migration_url
    get_settings.cache_clear()


@pytest.fixture
def session(test_database_url: str) -> Generator[Session, None, None]:
    engine = create_engine(test_database_url)
    connection = engine.connect()
    transaction = connection.begin()
    database_session = Session(
        bind=connection,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )

    try:
        yield database_session
    finally:
        database_session.close()
        transaction.rollback()
        connection.close()
        engine.dispose()


@pytest.fixture
def client(session: Session) -> Generator[TestClient, None, None]:
    def override_database_session() -> Generator[Session, None, None]:
        yield session

    app.dependency_overrides[get_database_session] = override_database_session
    app.state.test_session = session

    try:
        with TestClient(app, base_url="http://localhost") as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_database_session, None)
        del app.state.test_session
