"""add kb.is_public + training options columns

Revision ID: e5c8a1f4b210
Revises: d41a7b9c2f06
Create Date: 2026-06-14 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e5c8a1f4b210"
down_revision: Union[str, None] = "d41a7b9c2f06"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_col(table: str, col: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    try:
        return col in {c["name"] for c in insp.get_columns(table)}
    except Exception:
        return False


def upgrade() -> None:
    if not _has_col("knowledge_bases", "is_public"):
        op.add_column(
            "knowledge_bases",
            sa.Column("is_public", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        )
    for table in ("training_questions", "question_bank"):
        if not _has_col(table, "options"):
            op.add_column(table, sa.Column("options", sa.JSON(), nullable=True))


def downgrade() -> None:
    for table in ("training_questions", "question_bank"):
        if _has_col(table, "options"):
            op.drop_column(table, "options")
    if _has_col("knowledge_bases", "is_public"):
        op.drop_column("knowledge_bases", "is_public")
