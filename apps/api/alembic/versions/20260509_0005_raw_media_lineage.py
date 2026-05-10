"""s2 raw media lineage schema

Revision ID: 20260509_0005
Revises: 20260509_0004
Create Date: 2026-05-09
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260509_0005"
down_revision = "20260509_0004"
branch_labels = None
depends_on = None


def _json_type():
    return sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def _json_default(bind):
    return sa.text("'{}'::jsonb") if bind.dialect.name == "postgresql" else sa.text("'{}'")


def _bool_false(bind):
    return sa.text("false") if bind.dialect.name == "postgresql" else sa.text("0")


def upgrade() -> None:
    bind = op.get_bind()
    json_type = _json_type()
    json_default = _json_default(bind)
    bool_false = _bool_false(bind)

    op.create_table(
        "raw_records",
        sa.Column("id", sa.String(length=120), primary_key=True),
        sa.Column("tenant_id", sa.String(length=80), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("data_source_id", sa.String(length=120), sa.ForeignKey("data_sources.id"), nullable=False),
        sa.Column("collection_run_id", sa.String(length=120), sa.ForeignKey("collection_runs.id"), nullable=False),
        sa.Column("source_type", sa.String(length=60), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("content_hash", sa.String(length=120), nullable=False),
        sa.Column("dedupe_key", sa.String(length=240), nullable=True),
        sa.Column("rss_guid_key", sa.String(length=240), nullable=True),
        sa.Column("rss_link_key", sa.String(length=240), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("is_synthetic", sa.Boolean(), nullable=False, server_default=bool_false),
        sa.Column("city_id", sa.String(length=80), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payload", json_type, nullable=False, server_default=json_default),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_raw_records_tenant_id", "raw_records", ["tenant_id"])
    op.create_index("ix_raw_records_data_source_id", "raw_records", ["data_source_id"])
    op.create_index("ix_raw_records_collection_run_id", "raw_records", ["collection_run_id"])
    op.create_index("ix_raw_records_dedupe_key", "raw_records", ["dedupe_key"])
    op.create_index("ix_raw_records_rss_guid_key", "raw_records", ["rss_guid_key"])
    op.create_index("ix_raw_records_rss_link_key", "raw_records", ["rss_link_key"])
    op.create_index("ux_raw_records_rss_guid_key", "raw_records", ["data_source_id", "source_type", "rss_guid_key"], unique=True)
    op.create_index("ux_raw_records_rss_link_key", "raw_records", ["data_source_id", "source_type", "rss_link_key"], unique=True)

    op.create_table(
        "raw_record_payloads",
        sa.Column("id", sa.String(length=120), primary_key=True),
        sa.Column("raw_record_id", sa.String(length=120), sa.ForeignKey("raw_records.id"), nullable=False),
        sa.Column("content_text", sa.Text(), nullable=False),
        sa.Column("masked_text", sa.Text(), nullable=False),
        sa.Column("payload", json_type, nullable=False, server_default=json_default),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_raw_record_payloads_raw_record_id", "raw_record_payloads", ["raw_record_id"])

    op.create_table(
        "raw_record_labels",
        sa.Column("id", sa.String(length=120), primary_key=True),
        sa.Column("raw_record_id", sa.String(length=120), sa.ForeignKey("raw_records.id"), nullable=False),
        sa.Column("label", sa.String(length=120), nullable=False),
        sa.Column("actor_id", sa.String(length=120), nullable=True),
        sa.Column("reason", sa.String(length=240), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_raw_record_labels_raw_record_id", "raw_record_labels", ["raw_record_id"])

    op.create_table(
        "media_assets",
        sa.Column("id", sa.String(length=120), primary_key=True),
        sa.Column("raw_record_id", sa.String(length=120), sa.ForeignKey("raw_records.id"), nullable=False),
        sa.Column("media_type", sa.String(length=40), nullable=False),
        sa.Column("uri", sa.String(length=400), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("is_synthetic", sa.Boolean(), nullable=False, server_default=bool_false),
        sa.Column("payload", json_type, nullable=False, server_default=json_default),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_media_assets_raw_record_id", "media_assets", ["raw_record_id"])

    op.create_table(
        "media_processing_runs",
        sa.Column("id", sa.String(length=120), primary_key=True),
        sa.Column("media_asset_id", sa.String(length=120), sa.ForeignKey("media_assets.id"), nullable=False),
        sa.Column("processor", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("output", json_type, nullable=False, server_default=json_default),
        sa.Column("trace_id", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_media_processing_runs_media_asset_id", "media_processing_runs", ["media_asset_id"])

    op.create_table(
        "lineage_edges",
        sa.Column("id", sa.String(length=120), primary_key=True),
        sa.Column("from_object_type", sa.String(length=80), nullable=False),
        sa.Column("from_object_id", sa.String(length=120), nullable=False),
        sa.Column("to_object_type", sa.String(length=80), nullable=False),
        sa.Column("to_object_id", sa.String(length=120), nullable=False),
        sa.Column("relation", sa.String(length=80), nullable=False),
        sa.Column("is_synthetic", sa.Boolean(), nullable=False, server_default=bool_false),
        sa.Column("payload", json_type, nullable=False, server_default=json_default),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_lineage_from", "lineage_edges", ["from_object_type", "from_object_id"])
    op.create_index("ix_lineage_to", "lineage_edges", ["to_object_type", "to_object_id"])


def downgrade() -> None:
    raise RuntimeError("Downgrade is intentionally disabled for S2 raw media lineage.")
