"""create busy blocks

Revision ID: 0002_create_busy_blocks
Revises: 0001_create_users
Create Date: 2026-09-18
"""

import sqlalchemy as sa
from alembic import op

revision = "0002_create_busy_blocks"
down_revision = "0001_create_users"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "busy_blocks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("is_recurring", sa.Boolean(), nullable=False),
        sa.Column("weekday", sa.Integer(), nullable=True),
        sa.Column("start_time", sa.Time(), nullable=True),
        sa.Column("end_time", sa.Time(), nullable=True),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("external_event_id", sa.String(length=1024), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "source IN ('timetable', 'manual', 'google_calendar')", name="busy_blocks_source"
        ),
        sa.CheckConstraint(
            "weekday IS NULL OR weekday BETWEEN 0 AND 6", name="busy_blocks_weekday"
        ),
        sa.CheckConstraint(
            "(is_recurring = true AND weekday IS NOT NULL AND start_time IS NOT NULL "
            "AND end_time IS NOT NULL AND starts_at IS NULL AND ends_at IS NULL) OR "
            "(is_recurring = false AND weekday IS NULL AND start_time IS NULL "
            "AND end_time IS NULL AND starts_at IS NOT NULL AND ends_at IS NOT NULL)",
            name="busy_blocks_schedule_shape",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_busy_blocks_user_id", "busy_blocks", ["user_id"])
    op.create_index("ix_busy_blocks_source", "busy_blocks", ["source"])
    op.create_index("ix_busy_blocks_external_event_id", "busy_blocks", ["external_event_id"])


def downgrade() -> None:
    op.drop_table("busy_blocks")
