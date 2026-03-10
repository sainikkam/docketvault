"""widen_source_system_to_text

The source_system column was VARCHAR(100), which is too narrow for
AI-parsed content from detailed letters. Widen to TEXT to match the
format_instructions and preservation_note columns.

Revision ID: h4c5d6e7f8a9
Revises: f2a3b4c5d6e7
Create Date: 2026-03-09 22:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "h4c5d6e7f8a9"
down_revision: Union[str, None] = "f2a3b4c5d6e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "requests",
        "source_system",
        type_=sa.Text(),
        existing_type=sa.String(100),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "requests",
        "source_system",
        type_=sa.String(100),
        existing_type=sa.Text(),
        existing_nullable=True,
    )
