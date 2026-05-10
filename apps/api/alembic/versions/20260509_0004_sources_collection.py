"""s2 sources collection schema

Revision ID: 20260509_0004
Revises: 20260509_0003
Create Date: 2026-05-09
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260509_0004"
down_revision = "20260509_0003"
branch_labels = None
depends_on = None


def _json_type():
    return sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def _json_default(bind):
    return sa.text("'{}'::jsonb") if bind.dialect.name == "postgresql" else sa.text("'{}'")


def _bool_false(bind):
    return sa.text("false") if bind.dialect.name == "postgresql" else sa.text("0")


def upgrade() -> None:
    bind = op.get_bind()
    json_type = _json_type()
    json_default = _json_default(bind)
    bool_false = _bool_false(bind)

    op.create_table(
        "data_sources",
        sa.Column("id", sa.String(length=120), primary_key=True),
        sa.Column("tenant_id", sa.String(length=80), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("source_type", sa.String(length=60), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("is_synthetic", sa.Boolean(), nullable=False, server_default=bool_false),
        sa.Column("policy", json_type, nullable=False, server_default=json_default),
        sa.Column("payload", json_type, nullable=False, server_default=json_default),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_data_sources_tenant_id", "data_sources", ["tenant_id"])

    op.create_table(
        "source_policies",
        sa.Column("id", sa.String(length=120), primary_key=True),
        sa.Column("data_source_id", sa.String(length=120), sa.ForeignKey("data_sources.id"), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("reason", sa.String(length=240), nullable=True),
        sa.Column("payload", json_type, nullable=False, server_default=json_default),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_source_policies_data_source_id", "source_policies", ["data_source_id"])

    op.create_table(
        "source_health",
        sa.Column("id", sa.String(length=120), primary_key=True),
        sa.Column("data_source_id", sa.String(length=120), sa.ForeignKey("data_sources.id"), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("last_run_id", sa.String(length=120), nullable=True),
        sa.Column("success_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failure_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error_code", sa.String(length=120), nullable=True),
        sa.Column("payload", json_type, nullable=False, server_default=json_default),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_source_health_data_source_id", "source_health", ["data_source_id"])

    op.create_table(
        "collection_jobs",
        sa.Column("id", sa.String(length=120), primary_key=True),
        sa.Column("tenant_id", sa.String(length=80), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("data_source_id", sa.String(length=120), sa.ForeignKey("data_sources.id"), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("schedule", sa.String(length=120), nullable=True),
        sa.Column("payload", json_type, nullable=False, server_default=json_default),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_collection_jobs_tenant_id", "collection_jobs", ["tenant_id"])
    op.create_index("ix_collection_jobs_data_source_id", "collection_jobs", ["data_source_id"])

    op.create_table(
        "collection_runs",
        sa.Column("id", sa.String(length=120), primary_key=True),
        sa.Column("collection_job_id", sa.String(length=120), sa.ForeignKey("collection_jobs.id"), nullable=False),
        sa.Column("data_source_id", sa.String(length=120), sa.ForeignKey("data_sources.id"), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("record_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_code", sa.String(length=120), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("trace_id", sa.String(length=120), nullable=True),
        sa.Column("payload", json_type, nullable=False, server_default=json_default),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_collection_runs_collection_job_id", "collection_runs", ["collection_job_id"])
    op.create_index("ix_collection_runs_data_source_id", "collection_runs", ["data_source_id"])

    op.create_table(
        "collection_run_events",
        sa.Column("id", sa.String(length=120), primary_key=True),
        sa.Column("collection_run_id", sa.String(length=120), sa.ForeignKey("collection_runs.id"), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("payload", json_type, nullable=False, server_default=json_default),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    raise RuntimeError("Downgrade is intentionally disabled for S2 sources collection.")
