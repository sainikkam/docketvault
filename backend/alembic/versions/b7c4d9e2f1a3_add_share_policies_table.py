"""add_share_policies_table

Revision ID: b7c4d9e2f1a3
Revises: a3f8e12b7c4d
Create Date: 2026-03-08 16:30:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = "b7c4d9e2f1a3"
down_revision: Union[str, None] = "a3f8e12b7c4d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "share_policies",
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("matter_id", sa.Uuid(), nullable=False),
        sa.Column("artifact_id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "state",
            sqlmodel.sql.sqltypes.AutoString(length=20),
            nullable=False,
        ),
        sa.Column("is_sensitive", sa.Boolean(), nullable=False),
        sa.Column("sensitivity_acknowledged", sa.Boolean(), nullable=False),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["matter_id"], ["matters.id"]),
        sa.ForeignKeyConstraint(["artifact_id"], ["artifacts.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("matter_id", "artifact_id"),
    )
    op.create_index(
        op.f("ix_share_policies_matter_id"),
        "share_policies",
        ["matter_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_share_policies_artifact_id"),
        "share_policies",
        ["artifact_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_share_policies_artifact_id"), table_name="share_policies")
    op.drop_index(op.f("ix_share_policies_matter_id"), table_name="share_policies")
    op.drop_table("share_policies")
