"""add_structured_request_fields_and_templates

Adds structured RFP fields to the requests table (category, date_range,
keywords, source_system, format_instructions, preservation_note) and
creates the request_templates table for reusable firm-level templates.

Revision ID: e1f2a3b4c5d6
Revises: d9e6f5a3b4c2
Create Date: 2026-03-09 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = "e1f2a3b4c5d6"
down_revision: Union[str, None] = "d9e6f5a3b4c2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -- Add structured fields to existing requests table --
    op.add_column(
        "requests",
        sa.Column("category", sqlmodel.sql.sqltypes.AutoString(length=50), nullable=True),
    )
    op.add_column(
        "requests",
        sa.Column("date_range_start", sa.Date(), nullable=True),
    )
    op.add_column(
        "requests",
        sa.Column("date_range_end", sa.Date(), nullable=True),
    )
    op.add_column(
        "requests",
        sa.Column("keywords", sa.JSON(), nullable=True, server_default="[]"),
    )
    op.add_column(
        "requests",
        sa.Column("source_system", sqlmodel.sql.sqltypes.AutoString(length=100), nullable=True),
    )
    op.add_column(
        "requests",
        sa.Column("format_instructions", sa.Text(), nullable=True),
    )
    op.add_column(
        "requests",
        sa.Column("preservation_note", sa.Text(), nullable=True),
    )

    # -- Create request_templates table --
    op.create_table(
        "request_templates",
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("firm_id", sa.Uuid(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
        sa.Column("category", sqlmodel.sql.sqltypes.AutoString(length=50), nullable=False),
        sa.Column("default_description", sa.Text(), nullable=True),
        sa.Column("default_format_instructions", sa.Text(), nullable=True),
        sa.Column("default_preservation_note", sa.Text(), nullable=True),
        sa.Column(
            "default_source_system",
            sqlmodel.sql.sqltypes.AutoString(length=100),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(["firm_id"], ["firms.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_request_templates_firm_id"),
        "request_templates",
        ["firm_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_request_templates_firm_id"), table_name="request_templates")
    op.drop_table("request_templates")

    op.drop_column("requests", "preservation_note")
    op.drop_column("requests", "format_instructions")
    op.drop_column("requests", "source_system")
    op.drop_column("requests", "keywords")
    op.drop_column("requests", "date_range_end")
    op.drop_column("requests", "date_range_start")
    op.drop_column("requests", "category")
