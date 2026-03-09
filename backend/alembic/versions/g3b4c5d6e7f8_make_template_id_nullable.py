"""make_template_id_nullable

Matter templates add no value in the current workflow.
Make template_id optional so lawyers can create matters directly
after setting up a firm, without needing to create a template first.

Revision ID: g3b4c5d6e7f8
Revises: f2a3b4c5d6e7
Create Date: 2026-03-09 16:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "g3b4c5d6e7f8"
down_revision: Union[str, None] = "f2a3b4c5d6e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "matters",
        "template_id",
        existing_type=sa.Uuid(),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "matters",
        "template_id",
        existing_type=sa.Uuid(),
        nullable=False,
    )
