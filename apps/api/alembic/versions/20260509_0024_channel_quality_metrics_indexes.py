"""s2 channel quality metrics indexes

Revision ID: 20260509_0024
Revises: 20260509_0023
Create Date: 2026-05-10
"""

from __future__ import annotations

from alembic import op

revision = "20260509_0024"
down_revision = "20260509_0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    with op.get_context().autocommit_block():
        op.execute(
            """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_collection_runs_job_created_id
            ON collection_runs (collection_job_id, created_at DESC, id)
            """
        )
        op.execute(
            """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_collection_runs_source_created_id
            ON collection_runs (data_source_id, created_at DESC, id)
            """
        )
        op.execute(
            """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_raw_records_tenant_collection_run
            ON raw_records (tenant_id, collection_run_id)
            """
        )
        op.execute(
            """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_lineage_edges_to_object
            ON lineage_edges (to_object_type, to_object_id)
            """
        )
        op.execute(
            """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_lineage_edges_from_object
            ON lineage_edges (from_object_type, from_object_id)
            """
        )


def downgrade() -> None:
    raise RuntimeError("Downgrade is intentionally disabled for S2 channel quality metrics indexes.")
