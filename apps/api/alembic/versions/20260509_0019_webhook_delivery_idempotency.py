"""s2 webhook delivery idempotency

Revision ID: 20260509_0019
Revises: 20260509_0018
Create Date: 2026-05-10
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260509_0019"
down_revision = "20260509_0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("raw_records")}
    if "webhook_delivery_key" not in columns:
        op.add_column("raw_records", sa.Column("webhook_delivery_key", sa.String(length=240), nullable=True))
    indexes = {index["name"] for index in inspector.get_indexes("raw_records")}
    if "ix_raw_records_webhook_delivery_key" not in indexes:
        op.create_index("ix_raw_records_webhook_delivery_key", "raw_records", ["webhook_delivery_key"])
    if "ux_raw_records_webhook_delivery_key" not in indexes:
        op.create_index("ux_raw_records_webhook_delivery_key", "raw_records", ["data_source_id", "source_type", "webhook_delivery_key"], unique=True)


def downgrade() -> None:
    raise RuntimeError("Downgrade is intentionally disabled for S2 webhook delivery idempotency.")
