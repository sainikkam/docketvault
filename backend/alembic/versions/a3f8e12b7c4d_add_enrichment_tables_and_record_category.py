"""add_enrichment_tables_and_record_category

Revision ID: a3f8e12b7c4d
Revises: 7d2c7c7cee7f
Create Date: 2026-03-08 16:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = "a3f8e12b7c4d"
down_revision: Union[str, None] = "7d2c7c7cee7f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add category and relevance_score to records table
    op.add_column(
        "records",
        sa.Column(
            "category",
            sqlmodel.sql.sqltypes.AutoString(length=50),
            nullable=False,
            server_default="uncategorized",
        ),
    )
    op.add_column(
        "records",
        sa.Column("relevance_score", sa.Float(), nullable=False, server_default="0.0"),
    )

    # Create timeline_events table
    op.create_table(
        "timeline_events",
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("matter_id", sa.Uuid(), nullable=False),
        sa.Column(
            "event_type",
            sqlmodel.sql.sqltypes.AutoString(length=50),
            nullable=False,
        ),
        sa.Column(
            "title",
            sqlmodel.sql.sqltypes.AutoString(length=500),
            nullable=False,
        ),
        sa.Column("event_ts", sa.DateTime(), nullable=True),
        sa.Column("actors", sa.JSON(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column(
            "verification_state",
            sqlmodel.sql.sqltypes.AutoString(length=20),
            nullable=False,
        ),
        sa.Column("citations", sa.JSON(), nullable=True),
        sa.Column("related_record_ids", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["matter_id"], ["matters.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_timeline_events_matter_id"),
        "timeline_events",
        ["matter_id"],
        unique=False,
    )

    # Create missing_items table
    op.create_table(
        "missing_items",
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("matter_id", sa.Uuid(), nullable=False),
        sa.Column(
            "missing_type",
            sqlmodel.sql.sqltypes.AutoString(length=50),
            nullable=False,
        ),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "priority",
            sqlmodel.sql.sqltypes.AutoString(length=10),
            nullable=False,
        ),
        sa.Column(
            "status",
            sqlmodel.sql.sqltypes.AutoString(length=20),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["matter_id"], ["matters.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_missing_items_matter_id"),
        "missing_items",
        ["matter_id"],
        unique=False,
    )

    # Create intake_summaries table
    op.create_table(
        "intake_summaries",
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("matter_id", sa.Uuid(), nullable=False),
        sa.Column("case_overview", sa.Text(), nullable=True),
        sa.Column("key_timeline", sa.JSON(), nullable=True),
        sa.Column("open_questions", sa.JSON(), nullable=True),
        sa.Column("generated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["matter_id"], ["matters.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("matter_id"),
    )


def downgrade() -> None:
    op.drop_table("intake_summaries")
    op.drop_index(op.f("ix_missing_items_matter_id"), table_name="missing_items")
    op.drop_table("missing_items")
    op.drop_index(
        op.f("ix_timeline_events_matter_id"), table_name="timeline_events"
    )
    op.drop_table("timeline_events")
    op.drop_column("records", "relevance_score")
    op.drop_column("records", "category")
