"""FastAPI dependencies shared by routers."""

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.session import get_sessionmaker


def get_db() -> Iterator[Session]:
    """One database session per request, closed when the response is done.

    Routes here only read, so there's nothing to commit. Tests replace this dependency
    with their rolled-back test session via `app.dependency_overrides`.
    """
    with get_sessionmaker()() as session:
        yield session


DbSession = Annotated[Session, Depends(get_db)]
