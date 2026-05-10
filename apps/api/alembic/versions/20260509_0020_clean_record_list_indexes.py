"""s2 clean record list indexes

Revision ID: 20260509_0020
Revises: 20260509_0019
Create Date: 2026-05-10
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260509_0020"
down_revision = "20260509_0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    indexes = {index["name"] for index in inspector.get_indexes("raw_records")}
    if "ix_raw_records_tenant_created_id" not in indexes:
        op.create_index("ix_raw_records_tenant_created_id", "raw_records", ["tenant_id", "created_at", "id"])
    if "ix_raw_records_tenant_source_created" not in indexes:
        op.create_index("ix_raw_records_tenant_source_created", "raw_records", ["tenant_id", "data_source_id", "created_at", "id"])
    if "ix_raw_records_tenant_source_type_created" not in indexes:
        op.create_index("ix_raw_records_tenant_source_type_created", "raw_records", ["tenant_id", "source_type", "created_at", "id"])
    if "ix_raw_records_tenant_status_created" not in indexes:
        op.create_index("ix_raw_records_tenant_status_created", "raw_records", ["tenant_id", "status", "created_at", "id"])


def downgrade() -> None:
    raise RuntimeError("Downgrade is intentionally disabled for S2 clean record list indexes.")
