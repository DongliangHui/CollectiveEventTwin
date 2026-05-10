"""s2 quality issue tenant scope

Revision ID: 20260509_0023
Revises: 20260509_0022
Create Date: 2026-05-10
"""

from __future__ import annotations

from alembic import op

revision = "20260509_0023"
down_revision = "20260509_0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute("ALTER TABLE raw_record_quality_issues ADD COLUMN IF NOT EXISTS tenant_id VARCHAR(80)")
    op.execute(
        """
        UPDATE raw_record_quality_issues AS issue
        SET tenant_id = run.tenant_id
        FROM data_quality_runs AS run
        WHERE issue.data_quality_run_id = run.id
          AND issue.tenant_id IS NULL
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_raw_record_quality_issues_tenant_created
        ON raw_record_quality_issues (tenant_id, created_at DESC, id)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_raw_record_quality_issues_tenant_type_created
        ON raw_record_quality_issues (tenant_id, issue_type, created_at DESC, id)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_raw_record_quality_issues_tenant_severity_created
        ON raw_record_quality_issues (tenant_id, severity, created_at DESC, id)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_raw_record_quality_issues_tenant_run_created
        ON raw_record_quality_issues (tenant_id, data_quality_run_id, created_at DESC, id)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_raw_record_quality_issues_tenant_raw_created
        ON raw_record_quality_issues (tenant_id, raw_record_id, created_at DESC, id)
        """
    )


def downgrade() -> None:
    raise RuntimeError("Downgrade is intentionally disabled for S2 quality issue tenant scope.")
