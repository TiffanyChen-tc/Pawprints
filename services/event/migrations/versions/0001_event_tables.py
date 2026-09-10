from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0001_event_tables"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "categories",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("normalized_name", sa.String(length=120), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "normalized_name", name="uq_events_categories_user_normalized_name"),
        schema="events",
    )
    op.create_index("ix_events_categories_user_id", "categories", ["user_id"], schema="events")
    op.create_table(
        "events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("category_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("mood", sa.String(length=16), nullable=True),
        sa.Column("location_name", sa.String(length=255), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("timezone", sa.String(length=128), nullable=False),
        sa.Column("local_date", sa.Date(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["category_id"], ["events.categories.id"]),
        schema="events",
    )
    op.create_index("ix_events_events_user_id", "events", ["user_id"], schema="events")
    op.create_index("ix_events_events_category_id", "events", ["category_id"], schema="events")
    op.create_index("ix_events_events_occurred_at", "events", ["occurred_at"], schema="events")
    op.create_index("ix_events_events_local_date", "events", ["local_date"], schema="events")
    op.execute(
        """
        CREATE VIEW events.analytics_event_facts AS
        SELECT
          e.id AS event_id,
          e.user_id,
          e.category_id,
          c.name AS category_name,
          e.local_date
        FROM events.events e
        JOIN events.categories c ON c.id = e.category_id
        """
    )
    op.execute("GRANT SELECT ON events.analytics_event_facts TO pawprints_analytics_ro")


def downgrade() -> None:
    op.execute("REVOKE SELECT ON events.analytics_event_facts FROM pawprints_analytics_ro")
    op.execute("DROP VIEW events.analytics_event_facts")
    op.drop_index("ix_events_events_local_date", table_name="events", schema="events")
    op.drop_index("ix_events_events_occurred_at", table_name="events", schema="events")
    op.drop_index("ix_events_events_category_id", table_name="events", schema="events")
    op.drop_index("ix_events_events_user_id", table_name="events", schema="events")
    op.drop_table("events", schema="events")
    op.drop_index("ix_events_categories_user_id", table_name="categories", schema="events")
    op.drop_table("categories", schema="events")
