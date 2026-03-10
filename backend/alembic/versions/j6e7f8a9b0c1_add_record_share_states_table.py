"""add_record_share_states_table

Per-record sharing granularity: lets clients include/exclude individual
records within a multi-item artifact (e.g. specific emails in a JSONL).

Revision ID: j6e7f8a9b0c1
Revises: i5d6e7f8a9b0
Create Date: 2026-03-09 23:30:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "j6e7f8a9b0c1"
down_revision: Union[str, None] = "i5d6e7f8a9b0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "record_share_states",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("share_policy_id", sa.Uuid(), sa.ForeignKey("share_policies.id"), nullable=False),
        sa.Column("record_id", sa.Uuid(), sa.ForeignKey("records.id"), nullable=False),
        sa.Column("state", sa.String(20), nullable=False, server_default="included"),
        sa.UniqueConstraint("share_policy_id", "record_id"),
    )
    op.create_index("ix_record_share_states_share_policy_id", "record_share_states", ["share_policy_id"])
    op.create_index("ix_record_share_states_record_id", "record_share_states", ["record_id"])


def downgrade() -> None:
    op.drop_index("ix_record_share_states_record_id", "record_share_states")
    op.drop_index("ix_record_share_states_share_policy_id", "record_share_states")
    op.drop_table("record_share_states")
