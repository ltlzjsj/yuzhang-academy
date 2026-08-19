"""add training tables

Revision ID: c33f2e6c8a21
Revises: b7f3c2a1d9e4
Create Date: 2026-06-13 18:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c33f2e6c8a21"
down_revision: Union[str, None] = "b7f3c2a1d9e4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(name: str) -> bool:
    bind = op.get_bind()
    return name in sa.inspect(bind).get_table_names()


def upgrade() -> None:
    if not _has_table("training_sessions"):
        op.create_table(
            "training_sessions",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("title", sa.String(length=256), nullable=False),
            sa.Column("topic", sa.String(length=512), nullable=False),
            sa.Column("question_type", sa.String(length=64), nullable=False),
            sa.Column("difficulty", sa.String(length=32), nullable=False),
            sa.Column("question_count", sa.Integer(), nullable=False),
            sa.Column("kb_ids", sa.JSON(), nullable=True),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("total_score", sa.Float(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_training_sessions_user_id"), "training_sessions", ["user_id"], unique=False)

    if not _has_table("training_questions"):
        op.create_table(
            "training_questions",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("session_id", sa.Integer(), nullable=False),
            sa.Column("seq", sa.Integer(), nullable=False),
            sa.Column("question_type", sa.String(length=64), nullable=False),
            sa.Column("question", sa.Text(), nullable=False),
            sa.Column("reference_answer", sa.Text(), nullable=False),
            sa.Column("rubric", sa.Text(), nullable=False),
            sa.Column("max_score", sa.Float(), nullable=False),
            sa.Column("citations", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.ForeignKeyConstraint(["session_id"], ["training_sessions.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_training_questions_session_id"), "training_questions", ["session_id"], unique=False)

    if not _has_table("training_answers"):
        op.create_table(
            "training_answers",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("session_id", sa.Integer(), nullable=False),
            sa.Column("question_id", sa.Integer(), nullable=False),
            sa.Column("answer", sa.Text(), nullable=False),
            sa.Column("score", sa.Float(), nullable=False),
            sa.Column("feedback", sa.Text(), nullable=False),
            sa.Column("suggestion", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.ForeignKeyConstraint(["question_id"], ["training_questions.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["session_id"], ["training_sessions.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_training_answers_question_id"), "training_answers", ["question_id"], unique=False)
        op.create_index(op.f("ix_training_answers_session_id"), "training_answers", ["session_id"], unique=False)


def downgrade() -> None:
    if _has_table("training_answers"):
        op.drop_index(op.f("ix_training_answers_session_id"), table_name="training_answers")
        op.drop_index(op.f("ix_training_answers_question_id"), table_name="training_answers")
        op.drop_table("training_answers")
    if _has_table("training_questions"):
        op.drop_index(op.f("ix_training_questions_session_id"), table_name="training_questions")
        op.drop_table("training_questions")
    if _has_table("training_sessions"):
        op.drop_index(op.f("ix_training_sessions_user_id"), table_name="training_sessions")
        op.drop_table("training_sessions")
