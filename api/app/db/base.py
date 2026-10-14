from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Parent class of every table model. Alembic compares `Base.metadata` to the live
    database to autogenerate migrations, so a model must subclass this to be managed."""
