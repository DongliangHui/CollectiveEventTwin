"""s2 import processing run schema

Revision ID: 20260509_0006
Revises: 20260509_0005
Create Date: 2026-05-09
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260509_0006"
down_revision = "20260509_0005"
branch_labels = None
depends_on = None


def _json_type():
    return sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def _json_default(bind):
    return sa.text("'{}'::jsonb") if bind.dialect.name == "postgresql" else sa.text("'{}'")


def _list_default(bind):
    return sa.text("'[]'::jsonb") if bind.dialect.name == "postgresql" else sa.text("'[]'")


def _bool_false(bind):
    return sa.text("false") if bind.dialect.name == "postgresql" else sa.text("0")


def upgrade() -> None:
    bind = op.get_bind()
    json_type = _json_type()
    json_default = _json_default(bind)
    list_default = _list_default(bind)
    bool_false = _bool_false(bind)

    op.create_table(
        "import_runs",
        sa.Column("id", sa.String(length=120), primary_key=True),
        sa.Column("tenant_id", sa.String(length=80), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("data_source_id", sa.String(length=120), sa.ForeignKey("data_sources.id"), nullable=False),
        sa.Column("collection_run_id", sa.String(length=120), sa.ForeignKey("collection_runs.id"), nullable=True),
        sa.Column("import_type", sa.String(length=60), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("record_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("error_code", sa.String(length=120), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("is_synthetic", sa.Boolean(), nullable=False, server_default=bool_false),
        sa.Column("trace_id", sa.String(length=120), nullable=True),
        sa.Column("payload", json_type, nullable=False, server_default=json_default),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_import_runs_tenant_id", "import_runs", ["tenant_id"])
    op.create_index("ix_import_runs_data_source_id", "import_runs", ["data_source_id"])
    op.create_index("ix_import_runs_collection_run_id", "import_runs", ["collection_run_id"])

    op.create_table(
        "normalization_runs",
        sa.Column("id", sa.String(length=120), primary_key=True),
        sa.Column("tenant_id", sa.String(length=80), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("input_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("output_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("rule_version", sa.String(length=80), nullable=False),
        sa.Column("error_code", sa.String(length=120), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("trace_id", sa.String(length=120), nullable=True),
        sa.Column("payload", json_type, nullable=False, server_default=json_default),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_normalization_runs_tenant_id", "normalization_runs", ["tenant_id"])

    op.create_table(
        "raw_record_normalizations",
        sa.Column("id", sa.String(length=120), primary_key=True),
        sa.Column("normalization_run_id", sa.String(length=120), sa.ForeignKey("normalization_runs.id"), nullable=False),
        sa.Column("raw_record_id", sa.String(length=120), sa.ForeignKey("raw_records.id"), nullable=False),
        sa.Column("normalized_title", sa.String(length=240), nullable=False),
        sa.Column("normalized_text", sa.Text(), nullable=False),
        sa.Column("language", sa.String(length=40), nullable=False),
        sa.Column("region_id", sa.String(length=80), nullable=True),
        sa.Column("payload", json_type, nullable=False, server_default=json_default),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_raw_record_normalizations_run", "raw_record_normalizations", ["normalization_run_id"])
    op.create_index("ix_raw_record_normalizations_raw", "raw_record_normalizations", ["raw_record_id"])

    op.create_table(
        "deduplication_runs",
        sa.Column("id", sa.String(length=120), primary_key=True),
        sa.Column("tenant_id", sa.String(length=80), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("input_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("duplicate_group_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("rule_version", sa.String(length=80), nullable=False),
        sa.Column("error_code", sa.String(length=120), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("trace_id", sa.String(length=120), nullable=True),
        sa.Column("payload", json_type, nullable=False, server_default=json_default),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_deduplication_runs_tenant_id", "deduplication_runs", ["tenant_id"])

    op.create_table(
        "raw_record_dedup_groups",
        sa.Column("id", sa.String(length=120), primary_key=True),
        sa.Column("deduplication_run_id", sa.String(length=120), sa.ForeignKey("deduplication_runs.id"), nullable=False),
        sa.Column("group_key", sa.String(length=160), nullable=False),
        sa.Column("kept_raw_record_id", sa.String(length=120), sa.ForeignKey("raw_records.id"), nullable=False),
        sa.Column("duplicate_raw_record_ids", json_type, nullable=False, server_default=list_default),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("payload", json_type, nullable=False, server_default=json_default),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_raw_record_dedup_groups_run", "raw_record_dedup_groups", ["deduplication_run_id"])

    op.create_table(
        "data_quality_runs",
        sa.Column("id", sa.String(length=120), primary_key=True),
        sa.Column("tenant_id", sa.String(length=80), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("input_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("issue_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("rule_version", sa.String(length=80), nullable=False),
        sa.Column("error_code", sa.String(length=120), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("trace_id", sa.String(length=120), nullable=True),
        sa.Column("payload", json_type, nullable=False, server_default=json_default),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_data_quality_runs_tenant_id", "data_quality_runs", ["tenant_id"])

    op.create_table(
        "raw_record_quality_issues",
        sa.Column("id", sa.String(length=120), primary_key=True),
        sa.Column("data_quality_run_id", sa.String(length=120), sa.ForeignKey("data_quality_runs.id"), nullable=False),
        sa.Column("raw_record_id", sa.String(length=120), sa.ForeignKey("raw_records.id"), nullable=False),
        sa.Column("issue_type", sa.String(length=80), nullable=False),
        sa.Column("severity", sa.String(length=40), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("payload", json_type, nullable=False, server_default=json_default),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_raw_record_quality_issues_run", "raw_record_quality_issues", ["data_quality_run_id"])
    op.create_index("ix_raw_record_quality_issues_raw", "raw_record_quality_issues", ["raw_record_id"])


def downgrade() -> None:
    raise RuntimeError("Downgrade is intentionally disabled for S2 import processing runs.")
