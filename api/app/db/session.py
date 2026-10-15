"""Database engine and sessions for app code (API requests, ingest jobs).

Nothing connects at import time: the engine is built on first use, so code that merely
imports app modules (most tests, tooling) never needs Postgres running.

Tests don't use this module's engine; they get the `db_session` fixture from
`tests/conftest.py`, which points at a separate test database and rolls everything back.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings


@lru_cache
def get_engine() -> Engine:
    """The process-wide engine (it owns the connection pool), created on first call."""
    # pool_pre_ping: check each pooled connection with a cheap round-trip before handing it
    # out, so a connection Postgres has dropped (container restart, idle timeout) is quietly
    # replaced instead of failing the next query.
    return create_engine(get_settings().database_url, pool_pre_ping=True)


@lru_cache
def get_sessionmaker() -> sessionmaker[Session]:
    """The factory for new Sessions on `get_engine()` (the classic `SessionLocal`)."""
    # expire_on_commit=False: objects keep their loaded values after commit, so they can
    # still be read (e.g. returned from an endpoint) without a surprise reload query, or a
    # DetachedInstanceError once the session has closed.
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


@contextmanager
def session_scope() -> Iterator[Session]:
    """One unit of work: commits if the block finishes, rolls back if it raises.

        with session_scope() as session:
            session.add(league)

    Calling `session.commit()` inside the block is fine (e.g. once per league, so a long
    crawl keeps its progress if it dies halfway); the final commit covers the rest.
    """
    session = get_sessionmaker()()
    try:
        yield session
        session.commit()
    except BaseException:
        # BaseException, not Exception: Ctrl+C mid-crawl must roll back too, never leave
        # half a unit of work behind. Re-raised, so nothing is swallowed.
        session.rollback()
        raise
    finally:
        session.close()
