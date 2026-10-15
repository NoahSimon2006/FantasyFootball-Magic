"""Shared pytest fixtures.

The database fixtures are opt-in (none is autouse): only tests that ask for `db_session`
(or `db_engine`) touch Postgres, so every other test runs without Docker.

Database tests get their own database, `fantasy_magic_test`, never the dev database, and
every write a test makes is rolled back when the test ends.
"""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

# 127.0.0.1 and connect_timeout, never "localhost": see tasks/lessons.md (IPv6 hang).
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://fantasy:fantasy@127.0.0.1:5432/fantasy_magic_test?connect_timeout=10",
)

ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"


def _create_database_if_missing(url: str) -> None:
    """Create the test database on the first run; later runs reuse it."""
    target = make_url(url)
    name = target.database
    assert name, "TEST_DATABASE_URL must name a database"
    # CREATE DATABASE must be sent while connected to some *other* database ("postgres"
    # always exists), and it can't run inside a transaction, hence AUTOCOMMIT.
    admin_engine = create_engine(target.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with admin_engine.connect() as connection:
            exists = connection.scalar(
                text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": name}
            )
            if not exists:
                quoted = connection.dialect.identifier_preparer.quote(name)
                connection.execute(text(f"CREATE DATABASE {quoted}"))
    finally:
        admin_engine.dispose()


@pytest.fixture(scope="session")
def alembic_config() -> Config:
    """Alembic's config from alembic.ini, pointed at the test database."""
    config = Config(str(ALEMBIC_INI))
    config.attributes["database_url"] = TEST_DATABASE_URL
    return config


@pytest.fixture(scope="session")
def db_engine(alembic_config: Config) -> Iterator[Engine]:
    """An Engine on the test database, migrated to the latest revision.

    The schema is built by running the real migrations (not `Base.metadata.create_all`),
    so every test run also proves the migrations work.
    """
    _create_database_if_missing(TEST_DATABASE_URL)
    command.upgrade(alembic_config, "head")
    engine = create_engine(TEST_DATABASE_URL)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(db_engine: Engine) -> Iterator[Session]:
    """A Session whose every write, even a committed one, is undone when the test ends.

    The test runs inside one outer transaction that is always rolled back. The Session
    joins it in "create_savepoint" mode, so its own commit() and rollback() only release
    or roll back a SAVEPOINT inside that transaction: code under test can commit as usual.
    """
    with db_engine.connect() as connection:
        transaction = connection.begin()
        session = Session(bind=connection, join_transaction_mode="create_savepoint")
        try:
            yield session
        finally:
            session.close()
            transaction.rollback()
