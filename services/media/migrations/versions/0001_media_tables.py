from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0001_media_tables"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "event_media",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("storage_key", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=64), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("event_id", "display_order", name="uq_media_event_media_event_display_order"),
        sa.UniqueConstraint("storage_key", name="uq_media_event_media_storage_key"),
        schema="media",
    )
    op.create_index("ix_media_event_media_event_id", "event_media", ["event_id"], schema="media")


def downgrade() -> None:
    op.drop_index("ix_media_event_media_event_id", table_name="event_media", schema="media")
    op.drop_table("event_media", schema="media")
