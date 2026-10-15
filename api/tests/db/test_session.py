"""session_scope() commits a block that finishes and rolls back a block that raises."""

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.db import session as session_module
from app.db.models import CrawlUser
from app.db.session import session_scope


@pytest.fixture
def scope_in_test_transaction(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    """Make session_scope() open its sessions inside the test's rolled-back transaction.

    Normally it talks to the dev database; here it joins `db_session`'s connection the same
    way `db_session` does, so whatever it commits is still undone after the test.
    """
    factory = sessionmaker(bind=db_session.get_bind(), join_transaction_mode="create_savepoint")
    monkeypatch.setattr(session_module, "get_sessionmaker", lambda: factory)


def count_users(session: Session, user_id: str) -> int:
    statement = select(func.count()).select_from(CrawlUser).where(CrawlUser.user_id == user_id)
    return session.execute(statement).scalar_one()


@pytest.mark.usefixtures("scope_in_test_transaction")
def test_session_scope_commits_when_the_block_finishes(db_session: Session) -> None:
    with session_scope() as session:
        session.add(CrawlUser(user_id="test-scope-ok"))

    assert count_users(db_session, "test-scope-ok") == 1


@pytest.mark.usefixtures("scope_in_test_transaction")
def test_session_scope_rolls_back_when_the_block_raises(db_session: Session) -> None:
    with pytest.raises(RuntimeError, match="crawl died"):
        with session_scope() as session:
            session.add(CrawlUser(user_id="test-scope-fail"))
            session.flush()  # the INSERT really reaches Postgres before the failure
            raise RuntimeError("crawl died halfway")

    assert count_users(db_session, "test-scope-fail") == 0
