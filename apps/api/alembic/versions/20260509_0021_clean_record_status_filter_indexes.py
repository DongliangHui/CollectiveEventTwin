"""s2 clean record status filter indexes

Revision ID: 20260509_0021
Revises: 20260509_0020
Create Date: 2026-05-10
"""

from __future__ import annotations

from alembic import op

revision = "20260509_0021"
down_revision = "20260509_0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_raw_records_tenant_semantic_status_created
        ON raw_records (tenant_id, ((payload #>> '{semantic_dedupe_records,status}')), created_at DESC, id)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_raw_records_tenant_decision_status_created
        ON raw_records (tenant_id, ((payload #>> '{dedupe_decision,status}')), created_at DESC, id)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_raw_records_tenant_rule_dedupe_status_created
        ON raw_records (tenant_id, ((payload #>> '{dedupe_by_hash_and_external_id,status}')), created_at DESC, id)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_raw_records_tenant_duplicate_of_created
        ON raw_records (tenant_id, ((payload #>> '{duplicate_of}')), created_at DESC, id)
        WHERE payload ? 'duplicate_of'
        """
    )


def downgrade() -> None:
    raise RuntimeError("Downgrade is intentionally disabled for S2 clean record status filter indexes.")
