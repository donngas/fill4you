"""add Google Calendar sync storage

Revision ID: 0004_add_google_calendar_sync
Revises: 0003_create_bookmarklet_tokens
Create Date: 2026-09-18
"""

import sqlalchemy as sa
from alembic import op

revision = "0004_add_google_calendar_sync"
down_revision = "0003_create_bookmarklet_tokens"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "busy_blocks",
        sa.Column("is_locally_modified", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.create_table(
        "google_oauth_tokens",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("encrypted_token", sa.String(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )
    op.create_table(
        "google_calendar_event_states",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("external_event_id", sa.String(length=1024), nullable=False),
        sa.Column("is_excluded", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "external_event_id"),
    )
    op.create_index(
        "ix_google_calendar_event_states_user_id", "google_calendar_event_states", ["user_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_google_calendar_event_states_user_id", "google_calendar_event_states")
    op.drop_table("google_calendar_event_states")
    op.drop_table("google_oauth_tokens")
    op.drop_column("busy_blocks", "is_locally_modified")
