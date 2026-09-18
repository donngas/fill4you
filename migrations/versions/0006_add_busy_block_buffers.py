"""add busy block buffers

Revision ID: 0006_add_busy_block_buffers
Revises: 0005_calendar_selection
Create Date: 2026-09-19
"""

import sqlalchemy as sa
from alembic import op

revision = "0006_add_busy_block_buffers"
down_revision = "0005_calendar_selection"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "busy_blocks",
        sa.Column("before_buffer_minutes", sa.Integer(), server_default="15", nullable=False),
    )
    op.add_column(
        "busy_blocks",
        sa.Column("after_buffer_minutes", sa.Integer(), server_default="15", nullable=False),
    )
    op.create_table(
        "busy_block_buffer_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("before_buffer_minutes", sa.Integer(), server_default="15", nullable=False),
        sa.Column("after_buffer_minutes", sa.Integer(), server_default="15", nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "source IN ('timetable', 'manual', 'google_calendar')", name="buffer_settings_source"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "source"),
    )
    op.create_index(
        "ix_busy_block_buffer_settings_user_id", "busy_block_buffer_settings", ["user_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_busy_block_buffer_settings_user_id", "busy_block_buffer_settings")
    op.drop_table("busy_block_buffer_settings")
    op.drop_column("busy_blocks", "after_buffer_minutes")
    op.drop_column("busy_blocks", "before_buffer_minutes")
