"""add question_bank table

Revision ID: d41a7b9c2f06
Revises: c33f2e6c8a21
Create Date: 2026-06-13 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d41a7b9c2f06"
down_revision: Union[str, None] = "c33f2e6c8a21"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(name: str) -> bool:
    bind = op.get_bind()
    return name in sa.inspect(bind).get_table_names()


def upgrade() -> None:
    if not _has_table("question_bank"):
        op.create_table(
            "question_bank",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("kb_id", sa.Integer(), nullable=False),
            sa.Column("topic", sa.String(length=512), nullable=False),
            sa.Column("question_type", sa.String(length=64), nullable=False),
            sa.Column("difficulty", sa.String(length=32), nullable=False),
            sa.Column("question", sa.Text(), nullable=False),
            sa.Column("reference_answer", sa.Text(), nullable=False),
            sa.Column("rubric", sa.Text(), nullable=False),
            sa.Column("max_score", sa.Float(), nullable=False),
            sa.Column("citations", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_question_bank_kb_id"), "question_bank", ["kb_id"], unique=False)


def downgrade() -> None:
    if _has_table("question_bank"):
        op.drop_index(op.f("ix_question_bank_kb_id"), table_name="question_bank")
        op.drop_table("question_bank")
