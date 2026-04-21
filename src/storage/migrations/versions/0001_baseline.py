"""Baseline — create all tables from current ORM metadata.

Revision ID: 0001_baseline
Revises:
Create Date: 2026-04-21

This is a squash of the pre-Alembic schema. It stamps an empty DB with the
full current shape via Base.metadata.create_all(). Subsequent schema changes
MUST be authored as regular Alembic revisions (op.create_table / op.add_column
/ etc.), not added here.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

from src.storage.models import Base

revision: str = "0001_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    Base.metadata.create_all(op.get_bind(), checkfirst=True)


def downgrade() -> None:
    Base.metadata.drop_all(op.get_bind())
