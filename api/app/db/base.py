from datetime import datetime

from sqlalchemy import DateTime
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Parent class of every table model. Alembic compares `Base.metadata` to the live
    database to autogenerate migrations, so a model must subclass this to be managed."""

    # Every `Mapped[datetime]` column is timezone-aware (Postgres `timestamptz`), so a
    # stored time always means one exact instant, regardless of the server's clock zone.
    type_annotation_map = {datetime: DateTime(timezone=True)}
