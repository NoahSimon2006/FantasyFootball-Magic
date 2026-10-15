"""Alembic migration environment.

The database URL comes from the app's Settings (env var DATABASE_URL), not alembic.ini,
so migrations and the API can never point at different databases. The one exception is
programmatic callers: the test suite sets `config.attributes["database_url"]` to migrate
its own separate test database.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

# Importing the models module is what registers every table on Base.metadata. Without it
# the metadata is empty, and autogenerate would "helpfully" emit DROP TABLE for everything.
import app.db.models  # noqa: F401
from app.config import get_settings
from app.db.base import Base

config = context.config

if config.config_file_name is not None:
    # disable_existing_loggers=False: the default disables every logger created before this
    # call. When tests run migrations in-process, that silently mutes the app's loggers for
    # the rest of the run, so pytest's caplog in later tests captures nothing.
    fileConfig(config.config_file_name, disable_existing_loggers=False)

# Autogenerate diffs this (every model that subclasses Base) against the live database.
target_metadata = Base.metadata

database_url: str = config.attributes.get("database_url") or get_settings().database_url


def run_migrations_offline() -> None:
    """Print the migration SQL instead of running it (`alembic upgrade head --sql`)."""
    context.configure(
        url=database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Connect to the database and apply migrations."""
    engine = create_engine(database_url, poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
