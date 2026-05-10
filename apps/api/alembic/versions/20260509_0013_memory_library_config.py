"""s7b memory library config schema

Revision ID: 20260509_0013
Revises: 20260509_0012
Create Date: 2026-05-09
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260509_0013"
down_revision = "20260509_0012"
branch_labels = None
depends_on = None


def _json_type():
    return sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def _json_default(bind):
    return sa.text("'{}'::jsonb") if bind.dialect.name == "postgresql" else sa.text("'{}'")


def _list_default(bind):
    return sa.text("'[]'::jsonb") if bind.dialect.name == "postgresql" else sa.text("'[]'")


def upgrade() -> None:
    bind = op.get_bind()
    json_type = _json_type()
    json_default = _json_default(bind)
    list_default = _list_default(bind)

    op.create_table(
        "retrospectives",
        sa.Column("id", sa.String(length=120), primary_key=True),
        sa.Column("tenant_id", sa.String(length=80), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("report_id", sa.String(length=100), sa.ForeignKey("reports.id"), nullable=False),
        sa.Column("case_id", sa.String(length=80), sa.ForeignKey("cases.id"), nullable=False),
        sa.Column("status", sa.String(length=60), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("review_id", sa.String(length=120), sa.ForeignKey("reviews.id"), nullable=True),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("source_refs", json_type, nullable=False, server_default=list_default),
        sa.Column("payload", json_type, nullable=False, server_default=json_default),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_retrospectives_tenant_id", "retrospectives", ["tenant_id"])
    op.create_index("ix_retrospectives_report_id", "retrospectives", ["report_id"])
    op.create_index("ix_retrospectives_case_id", "retrospectives", ["case_id"])

    op.create_table(
        "knowledge_items",
        sa.Column("id", sa.String(length=120), primary_key=True),
        sa.Column("tenant_id", sa.String(length=80), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("retrospective_id", sa.String(length=120), sa.ForeignKey("retrospectives.id"), nullable=False),
        sa.Column("report_id", sa.String(length=100), sa.ForeignKey("reports.id"), nullable=False),
        sa.Column("case_id", sa.String(length=80), sa.ForeignKey("cases.id"), nullable=False),
        sa.Column("status", sa.String(length=60), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source_refs", json_type, nullable=False, server_default=list_default),
        sa.Column("payload", json_type, nullable=False, server_default=json_default),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_knowledge_items_tenant_id", "knowledge_items", ["tenant_id"])
    op.create_index("ix_knowledge_items_retrospective_id", "knowledge_items", ["retrospective_id"])

    op.create_table(
        "case_library_entries",
        sa.Column("id", sa.String(length=120), primary_key=True),
        sa.Column("tenant_id", sa.String(length=80), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("case_id", sa.String(length=80), sa.ForeignKey("cases.id"), nullable=False),
        sa.Column("retrospective_id", sa.String(length=120), sa.ForeignKey("retrospectives.id"), nullable=False),
        sa.Column("knowledge_item_id", sa.String(length=120), sa.ForeignKey("knowledge_items.id"), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("status", sa.String(length=60), nullable=False),
        sa.Column("tags", json_type, nullable=False, server_default=list_default),
        sa.Column("source_refs", json_type, nullable=False, server_default=list_default),
        sa.Column("payload", json_type, nullable=False, server_default=json_default),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_case_library_entries_tenant_id", "case_library_entries", ["tenant_id"])
    op.create_index("ix_case_library_entries_knowledge_item_id", "case_library_entries", ["knowledge_item_id"])
    op.create_index("ix_case_library_entries_retrospective_id", "case_library_entries", ["retrospective_id"])

    op.create_table(
        "case_library_applications",
        sa.Column("id", sa.String(length=120), primary_key=True),
        sa.Column("tenant_id", sa.String(length=80), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("case_id", sa.String(length=80), sa.ForeignKey("cases.id"), nullable=False),
        sa.Column("case_library_entry_id", sa.String(length=120), sa.ForeignKey("case_library_entries.id"), nullable=False),
        sa.Column("target_object_type", sa.String(length=80), nullable=False),
        sa.Column("target_object_id", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=60), nullable=False),
        sa.Column("conflict_summary", json_type, nullable=False, server_default=json_default),
        sa.Column("source_refs", json_type, nullable=False, server_default=list_default),
        sa.Column("payload", json_type, nullable=False, server_default=json_default),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_case_library_applications_tenant_id", "case_library_applications", ["tenant_id"])
    op.create_index("ix_case_library_applications_case_library_entry_id", "case_library_applications", ["case_library_entry_id"])

    op.create_table(
        "config_versions",
        sa.Column("id", sa.String(length=120), primary_key=True),
        sa.Column("tenant_id", sa.String(length=80), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("config_type", sa.String(length=80), nullable=False),
        sa.Column("version", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=60), nullable=False),
        sa.Column("review_id", sa.String(length=120), sa.ForeignKey("reviews.id"), nullable=True),
        sa.Column("regression_workflow_run_id", sa.String(length=100), sa.ForeignKey("workflow_runs.id"), nullable=True),
        sa.Column("parent_version_id", sa.String(length=120), sa.ForeignKey("config_versions.id"), nullable=True),
        sa.Column("input_refs", json_type, nullable=False, server_default=list_default),
        sa.Column("impact_scope", json_type, nullable=False, server_default=json_default),
        sa.Column("payload", json_type, nullable=False, server_default=json_default),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_config_versions_tenant_id", "config_versions", ["tenant_id"])
    op.create_index("ix_config_versions_regression_workflow_run_id", "config_versions", ["regression_workflow_run_id"])

    op.create_table(
        "config_releases",
        sa.Column("id", sa.String(length=120), primary_key=True),
        sa.Column("tenant_id", sa.String(length=80), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("config_version_id", sa.String(length=120), sa.ForeignKey("config_versions.id"), nullable=False),
        sa.Column("status", sa.String(length=60), nullable=False),
        sa.Column("impact_scope", json_type, nullable=False, server_default=json_default),
        sa.Column("payload", json_type, nullable=False, server_default=json_default),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_config_releases_tenant_id", "config_releases", ["tenant_id"])
    op.create_index("ix_config_releases_config_version_id", "config_releases", ["config_version_id"])


def downgrade() -> None:
    raise RuntimeError("Downgrade is intentionally disabled for S7B memory/library/config schema.")
