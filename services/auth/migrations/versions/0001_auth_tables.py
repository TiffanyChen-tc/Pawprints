from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0001_auth_tables"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("email", name="uq_auth_users_email"),
        schema="auth",
    )
    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("replaced_by_token_id", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["auth.users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["replaced_by_token_id"], ["auth.refresh_tokens.id"]),
        sa.UniqueConstraint("token_hash", name="uq_auth_refresh_tokens_token_hash"),
        schema="auth",
    )
    op.create_index("ix_auth_refresh_tokens_user_id", "refresh_tokens", ["user_id"], schema="auth")


def downgrade() -> None:
    op.drop_index("ix_auth_refresh_tokens_user_id", table_name="refresh_tokens", schema="auth")
    op.drop_table("refresh_tokens", schema="auth")
    op.drop_table("users", schema="auth")
