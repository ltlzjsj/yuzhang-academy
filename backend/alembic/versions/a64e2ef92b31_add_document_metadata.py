"""add document metadata

Revision ID: a64e2ef92b31
Revises: 7d5f0c81a7b2
Create Date: 2026-04-25 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a64e2ef92b31"
down_revision: Union[str, None] = "7d5f0c81a7b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {c["name"] for c in sa.inspect(bind).get_columns("documents")}
    if "metadata" not in columns:
        op.add_column("documents", sa.Column("metadata", sa.JSON(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    columns = {c["name"] for c in sa.inspect(bind).get_columns("documents")}
    if "metadata" in columns:
        op.drop_column("documents", "metadata")
