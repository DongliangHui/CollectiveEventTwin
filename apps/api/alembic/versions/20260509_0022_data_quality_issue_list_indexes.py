"""s2 data quality issue list indexes

Revision ID: 20260509_0022
Revises: 20260509_0021
Create Date: 2026-05-10
"""

from __future__ import annotations

from alembic import op

revision = "20260509_0022"
down_revision = "20260509_0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_data_quality_runs_tenant_created_id
        ON data_quality_runs (tenant_id, created_at DESC, id)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_raw_record_quality_issues_created_id
        ON raw_record_quality_issues (created_at DESC, id)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_raw_record_quality_issues_type_created
        ON raw_record_quality_issues (issue_type, created_at DESC, id)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_raw_record_quality_issues_severity_created
        ON raw_record_quality_issues (severity, created_at DESC, id)
        """
    )


def downgrade() -> None:
    raise RuntimeError("Downgrade is intentionally disabled for S2 data quality issue list indexes.")
