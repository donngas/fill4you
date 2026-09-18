"""create bookmarklet tokens

Revision ID: 0003_create_bookmarklet_tokens
Revises: 0002_create_busy_blocks
Create Date: 2026-09-18
"""

import sqlalchemy as sa
from alembic import op

revision = "0003_create_bookmarklet_tokens"
down_revision = "0002_create_busy_blocks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "bookmarklet_tokens",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(length=80), nullable=False),
        sa.Column("token_digest", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_digest"),
    )
    op.create_index("ix_bookmarklet_tokens_user_id", "bookmarklet_tokens", ["user_id"])
    op.create_index("ix_bookmarklet_tokens_token_digest", "bookmarklet_tokens", ["token_digest"])


def downgrade() -> None:
    op.drop_table("bookmarklet_tokens")
