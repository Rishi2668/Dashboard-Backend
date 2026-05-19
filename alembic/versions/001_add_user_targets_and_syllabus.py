"""Add target_marks, exam_date and syllabus tables

Revision ID: 001
Revises:
Create Date: 2026-05-19

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS target_marks DOUBLE PRECISION")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS exam_date DATE")


def downgrade() -> None:
    op.drop_column("users", "exam_date")
    op.drop_column("users", "target_marks")
