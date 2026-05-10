"""s3a city topic signal schema

Revision ID: 20260509_0007
Revises: 20260509_0006
Create Date: 2026-05-09
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260509_0007"
down_revision = "20260509_0006"
branch_labels = None
depends_on = None


def _json_type():
    return sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def _json_default(bind):
    return sa.text("'{}'::jsonb") if bind.dialect.name == "postgresql" else sa.text("'{}'")


def _list_default(bind):
    return sa.text("'[]'::jsonb") if bind.dialect.name == "postgresql" else sa.text("'[]'")


def upgrade() -> None:
    bind = op.get_bind()
    json_type = _json_type()
    json_default = _json_default(bind)
    list_default = _list_default(bind)

    op.create_table(
        "cities",
        sa.Column("id", sa.String(length=80), primary_key=True),
        sa.Column("tenant_id", sa.String(length=80), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("region_code", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False, server_default=sa.text("'active'")),
        sa.Column("payload", json_type, nullable=False, server_default=json_default),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_cities_tenant_id", "cities", ["tenant_id"])

    op.create_table(
        "topics",
        sa.Column("id", sa.String(length=120), primary_key=True),
        sa.Column("tenant_id", sa.String(length=80), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("city_id", sa.String(length=80), sa.ForeignKey("cities.id"), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("heat_score", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_from_type", sa.String(length=80), nullable=True),
        sa.Column("created_from_id", sa.String(length=120), nullable=True),
        sa.Column("payload", json_type, nullable=False, server_default=json_default),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_topics_tenant_id", "topics", ["tenant_id"])
    op.create_index("ix_topics_city_id", "topics", ["city_id"])

    op.create_table(
        "city_events",
        sa.Column("id", sa.String(length=120), primary_key=True),
        sa.Column("tenant_id", sa.String(length=80), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("city_id", sa.String(length=80), sa.ForeignKey("cities.id"), nullable=False),
        sa.Column("topic_id", sa.String(length=120), sa.ForeignKey("topics.id"), nullable=True),
        sa.Column("raw_record_id", sa.String(length=120), sa.ForeignKey("raw_records.id"), nullable=True),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("heat_score", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("risk_score", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("evidence_refs", json_type, nullable=False, server_default=list_default),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payload", json_type, nullable=False, server_default=json_default),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_city_events_tenant_id", "city_events", ["tenant_id"])
    op.create_index("ix_city_events_city_id", "city_events", ["city_id"])
    op.create_index("ix_city_events_topic_id", "city_events", ["topic_id"])
    op.create_index("ix_city_events_raw_record_id", "city_events", ["raw_record_id"], unique=True)

    op.create_table(
        "city_map_states",
        sa.Column("id", sa.String(length=120), primary_key=True),
        sa.Column("tenant_id", sa.String(length=80), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("city_id", sa.String(length=80), sa.ForeignKey("cities.id"), nullable=False),
        sa.Column("user_id", sa.String(length=100), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("layer_mode", sa.String(length=40), nullable=False),
        sa.Column("filters", json_type, nullable=False, server_default=json_default),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("payload", json_type, nullable=False, server_default=json_default),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_city_map_states_tenant_id", "city_map_states", ["tenant_id"])
    op.create_index("ix_city_map_states_city_id", "city_map_states", ["city_id"])
    op.create_index("ix_city_map_states_user_id", "city_map_states", ["user_id"])
    op.create_index("ux_city_map_states_city_user", "city_map_states", ["city_id", "user_id"], unique=True)

    op.add_column("signals", sa.Column("topic_id", sa.String(length=120), nullable=True))
    op.create_index("ix_signals_topic_id", "signals", ["topic_id"])
    if bind.dialect.name != "sqlite":
        op.create_foreign_key("fk_signals_topic_id_topics", "signals", "topics", ["topic_id"], ["id"])

    op.create_table(
        "signal_packages",
        sa.Column("id", sa.String(length=120), primary_key=True),
        sa.Column("tenant_id", sa.String(length=80), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("topic_id", sa.String(length=120), sa.ForeignKey("topics.id"), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("rule_version", sa.String(length=80), nullable=False),
        sa.Column("payload", json_type, nullable=False, server_default=json_default),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_signal_packages_tenant_id", "signal_packages", ["tenant_id"])
    op.create_index("ix_signal_packages_topic_id", "signal_packages", ["topic_id"])

    op.create_table(
        "signal_package_items",
        sa.Column("id", sa.String(length=120), primary_key=True),
        sa.Column("signal_package_id", sa.String(length=120), sa.ForeignKey("signal_packages.id"), nullable=False),
        sa.Column("signal_id", sa.String(length=100), sa.ForeignKey("signals.id"), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("payload", json_type, nullable=False, server_default=json_default),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_signal_package_items_package", "signal_package_items", ["signal_package_id"])
    op.create_index("ix_signal_package_items_signal", "signal_package_items", ["signal_id"])


def downgrade() -> None:
    raise RuntimeError("Downgrade is intentionally disabled for S3A city/topic/signal schema.")
