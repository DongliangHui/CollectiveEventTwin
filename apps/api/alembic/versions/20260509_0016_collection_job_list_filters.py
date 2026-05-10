"""s2 collection job list filters

Revision ID: 20260509_0016
Revises: 20260509_0015
Create Date: 2026-05-09
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260509_0016"
down_revision = "20260509_0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("collection_jobs", sa.Column("created_by_id", sa.String(length=100), sa.ForeignKey("users.id"), nullable=True))
    op.create_index("ix_collection_jobs_created_by_id", "collection_jobs", ["created_by_id"])
    op.create_index("ix_collection_jobs_status", "collection_jobs", ["status"])
    op.create_index("ix_collection_jobs_tenant_status_source_created", "collection_jobs", ["tenant_id", "status", "data_source_id", "created_at"])


def downgrade() -> None:
    raise RuntimeError("Downgrade is intentionally disabled for S2 collection job list filters.")
