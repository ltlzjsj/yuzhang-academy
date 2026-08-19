"""add activities table

Revision ID: f1a2b3c4d5e6
Revises: e5c8a1f4b210
Create Date: 2026-06-15 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, None] = "e5c8a1f4b210"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(table: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    try:
        return table in insp.get_table_names()
    except Exception:
        return False


def upgrade() -> None:
    if _has_table("activities"):
        return
    op.create_table(
        "activities",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("category", sa.String(length=32), nullable=False, server_default="书院公告"),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("summary", sa.String(length=512), nullable=False, server_default=""),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("event_date", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("period", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("place", sa.String(length=256), nullable=False, server_default=""),
        sa.Column("audience", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="open"),
        sa.Column("highlights", sa.JSON(), nullable=True),
        sa.Column("image", sa.String(length=512), nullable=False, server_default=""),
        sa.Column("is_published", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_activities_category", "activities", ["category"])
    op.create_index("ix_activities_is_published", "activities", ["is_published"])


def downgrade() -> None:
    if not _has_table("activities"):
        return
    op.drop_index("ix_activities_is_published", table_name="activities")
    op.drop_index("ix_activities_category", table_name="activities")
    op.drop_table("activities")
