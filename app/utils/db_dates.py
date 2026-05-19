"""Portable date filters for SQLAlchemy (PostgreSQL-safe)."""

from datetime import date

from sqlalchemy import Date, cast
from sqlalchemy.orm.attributes import InstrumentedAttribute
from sqlalchemy.sql.elements import ColumnElement


def created_on(column: InstrumentedAttribute, day: date) -> ColumnElement[bool]:
    """Match rows whose timestamp column falls on the given calendar day."""
    return cast(column, Date) == day


def created_since(column: InstrumentedAttribute, day: date) -> ColumnElement[bool]:
    """Match rows on or after the given calendar day."""
    return cast(column, Date) >= day
