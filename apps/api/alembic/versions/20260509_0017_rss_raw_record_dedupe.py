"""s2 rss raw record dedupe key

Revision ID: 20260509_0017
Revises: 20260509_0016
Create Date: 2026-05-10
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260509_0017"
down_revision = "20260509_0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("raw_records")}
    if "dedupe_key" not in columns:
        op.add_column("raw_records", sa.Column("dedupe_key", sa.String(length=240), nullable=True))
    indexes = {index["name"] for index in inspector.get_indexes("raw_records")}
    if "ix_raw_records_dedupe_key" not in indexes:
        op.create_index("ix_raw_records_dedupe_key", "raw_records", ["dedupe_key"])
    if "ux_raw_records_source_type_dedupe_key" not in indexes:
        op.create_index("ux_raw_records_source_type_dedupe_key", "raw_records", ["data_source_id", "source_type", "dedupe_key"], unique=True)


def downgrade() -> None:
    raise RuntimeError("Downgrade is intentionally disabled for S2 RSS raw record dedupe.")
