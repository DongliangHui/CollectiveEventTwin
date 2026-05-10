"""tenant scope metrics snapshots

Revision ID: 20260509_0025
Revises: 20260509_0024
Create Date: 2026-05-10
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260509_0025"
down_revision = "20260509_0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    op.add_column("metrics_snapshots", sa.Column("tenant_id", sa.String(length=80), nullable=True))
    if bind.dialect.name == "postgresql":
        op.create_foreign_key("fk_metrics_snapshots_tenant_id_tenants", "metrics_snapshots", "tenants", ["tenant_id"], ["id"])
        with op.get_context().autocommit_block():
            op.execute(
                """
                CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_metrics_snapshots_tenant_scope
                ON metrics_snapshots (tenant_id, metric_scope, captured_at DESC)
                """
            )
    else:
        op.create_index("ix_metrics_snapshots_tenant_scope", "metrics_snapshots", ["tenant_id", "metric_scope", "captured_at"])


def downgrade() -> None:
    raise RuntimeError("Downgrade is intentionally disabled for tenant-scoped metrics snapshots.")
