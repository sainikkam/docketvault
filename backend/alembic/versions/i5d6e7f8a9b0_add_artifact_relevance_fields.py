"""add_artifact_relevance_fields

Add category, relevance_score, relevance_rationale, and tags columns
to the artifacts table so the enrichment pipeline can score and
categorize artifacts directly (not just records).

Revision ID: i5d6e7f8a9b0
Revises: h4c5d6e7f8a9
Create Date: 2026-03-09 23:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "i5d6e7f8a9b0"
down_revision: Union[str, Sequence[str]] = ("h4c5d6e7f8a9", "g3b4c5d6e7f8")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "artifacts",
        sa.Column("category", sa.String(50), nullable=False, server_default="uncategorized"),
    )
    op.add_column(
        "artifacts",
        sa.Column("relevance_score", sa.Float(), nullable=False, server_default="0.0"),
    )
    op.add_column(
        "artifacts",
        sa.Column("relevance_rationale", sa.Text(), nullable=True),
    )
    op.add_column(
        "artifacts",
        sa.Column("tags", sa.JSON(), nullable=False, server_default="[]"),
    )


def downgrade() -> None:
    op.drop_column("artifacts", "tags")
    op.drop_column("artifacts", "relevance_rationale")
    op.drop_column("artifacts", "relevance_score")
    op.drop_column("artifacts", "category")
