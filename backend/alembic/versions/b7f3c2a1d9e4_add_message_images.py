"""add message images

Revision ID: b7f3c2a1d9e4
Revises: a64e2ef92b31
Create Date: 2026-06-02 21:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b7f3c2a1d9e4"
down_revision: Union[str, None] = "a64e2ef92b31"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {c["name"] for c in sa.inspect(bind).get_columns("messages")}
    if "images" not in columns:
        op.add_column("messages", sa.Column("images", sa.JSON(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    columns = {c["name"] for c in sa.inspect(bind).get_columns("messages")}
    if "images" in columns:
        op.drop_column("messages", "images")
