"""Portable SQL expressions (PostgreSQL-safe)."""

from sqlalchemy import case, func
from sqlalchemy.orm.attributes import InstrumentedAttribute
from sqlalchemy.sql.elements import ColumnElement


def sum_correct(column: InstrumentedAttribute) -> ColumnElement:
    """Sum 1 per row where a boolean correctness column is true."""
    return func.sum(case((column.is_(True), 1), else_=0))
