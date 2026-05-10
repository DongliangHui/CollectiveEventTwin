"""s2 data source versions schema

Revision ID: 20260509_0015
Revises: 20260509_0014
Create Date: 2026-05-09
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260509_0015"
down_revision = "20260509_0014"
branch_labels = None
depends_on = None


def _json_type():
    return sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def _json_default(bind):
    return sa.text("'{}'::jsonb") if bind.dialect.name == "postgresql" else sa.text("'{}'")


def upgrade() -> None:
    bind = op.get_bind()
    json_type = _json_type()
    json_default = _json_default(bind)

    op.create_table(
        "data_source_versions",
        sa.Column("id", sa.String(length=120), primary_key=True),
        sa.Column("tenant_id", sa.String(length=80), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("data_source_id", sa.String(length=120), sa.ForeignKey("data_sources.id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("config_hash", sa.String(length=120), nullable=False),
        sa.Column("policy_snapshot", json_type, nullable=False, server_default=json_default),
        sa.Column("payload", json_type, nullable=False, server_default=json_default),
        sa.Column("published_by_id", sa.String(length=100), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_data_source_versions_tenant_id", "data_source_versions", ["tenant_id"])
    op.create_index("ix_data_source_versions_data_source_id", "data_source_versions", ["data_source_id"])
    op.create_index("ix_data_source_versions_status", "data_source_versions", ["status"])


def downgrade() -> None:
    raise RuntimeError("Downgrade is intentionally disabled for S2 data source versions.")
