"""add qa_pairs_per_chunk

Revision ID: 7d5f0c81a7b2
Revises: 2d14cf1b066c
Create Date: 2026-04-25 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "7d5f0c81a7b2"
down_revision: Union[str, None] = "2d14cf1b066c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {c["name"] for c in sa.inspect(bind).get_columns("knowledge_bases")}
    if "qa_pairs_per_chunk" not in columns:
        op.add_column(
            "knowledge_bases",
            sa.Column("qa_pairs_per_chunk", sa.Integer(), nullable=False, server_default="2"),
        )
    op.alter_column("knowledge_bases", "qa_pairs_per_chunk", server_default=None)


def downgrade() -> None:
    bind = op.get_bind()
    columns = {c["name"] for c in sa.inspect(bind).get_columns("knowledge_bases")}
    if "qa_pairs_per_chunk" in columns:
        op.drop_column("knowledge_bases", "qa_pairs_per_chunk")
