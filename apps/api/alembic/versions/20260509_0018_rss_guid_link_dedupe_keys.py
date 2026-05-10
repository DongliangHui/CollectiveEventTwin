"""s2 rss guid and link dedupe keys

Revision ID: 20260509_0018
Revises: 20260509_0017
Create Date: 2026-05-10
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260509_0018"
down_revision = "20260509_0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("raw_records")}
    for column_name in ("rss_guid_key", "rss_link_key"):
        if column_name not in columns:
            op.add_column("raw_records", sa.Column(column_name, sa.String(length=240), nullable=True))
    indexes = {index["name"] for index in inspector.get_indexes("raw_records")}
    if "ix_raw_records_rss_guid_key" not in indexes:
        op.create_index("ix_raw_records_rss_guid_key", "raw_records", ["rss_guid_key"])
    if "ix_raw_records_rss_link_key" not in indexes:
        op.create_index("ix_raw_records_rss_link_key", "raw_records", ["rss_link_key"])
    if "ux_raw_records_rss_guid_key" not in indexes:
        op.create_index("ux_raw_records_rss_guid_key", "raw_records", ["data_source_id", "source_type", "rss_guid_key"], unique=True)
    if "ux_raw_records_rss_link_key" not in indexes:
        op.create_index("ux_raw_records_rss_link_key", "raw_records", ["data_source_id", "source_type", "rss_link_key"], unique=True)


def downgrade() -> None:
    raise RuntimeError("Downgrade is intentionally disabled for S2 RSS guid/link dedupe keys.")
