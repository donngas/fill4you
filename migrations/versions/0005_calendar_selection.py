"""add Google Calendar selection

Revision ID: 0005_calendar_selection
Revises: 0004_add_google_calendar_sync
Create Date: 2026-09-18
"""

import sqlalchemy as sa
from alembic import op

revision = "0005_calendar_selection"
down_revision = "0004_add_google_calendar_sync"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "google_calendars",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("external_calendar_id", sa.String(length=1024), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("is_primary", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("is_selected", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "external_calendar_id"),
    )
    op.create_index("ix_google_calendars_user_id", "google_calendars", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_google_calendars_user_id", "google_calendars")
    op.drop_table("google_calendars")
