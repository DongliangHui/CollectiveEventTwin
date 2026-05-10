"""s1 workflow ops contracts schema

Revision ID: 20260509_0003
Revises: 20260509_0002
Create Date: 2026-05-09
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260509_0003"
down_revision = "20260509_0002"
branch_labels = None
depends_on = None


def _json_type():
    return sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def _json_default(bind):
    if bind.dialect.name == "postgresql":
        return sa.text("'{}'::jsonb")
    return sa.text("'{}'")


def upgrade() -> None:
    bind = op.get_bind()
    json_type = _json_type()
    json_default = _json_default(bind)

    with op.batch_alter_table("workflow_runs") as batch:
        batch.add_column(sa.Column("tenant_id", sa.String(length=80), nullable=True))
        batch.add_column(sa.Column("started_by", sa.String(length=120), nullable=True))
        batch.add_column(sa.Column("trace_id", sa.String(length=120), nullable=True))
    op.create_index("ix_workflow_runs_tenant_id", "workflow_runs", ["tenant_id"])

    op.create_table(
        "workflow_run_events",
        sa.Column("id", sa.String(length=120), primary_key=True),
        sa.Column("workflow_run_id", sa.String(length=100), sa.ForeignKey("workflow_runs.id"), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("payload", json_type, nullable=False, server_default=json_default),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_workflow_run_events_workflow_run_id", "workflow_run_events", ["workflow_run_id"])

    op.create_table(
        "ops_error_queue",
        sa.Column("id", sa.String(length=120), primary_key=True),
        sa.Column("source", sa.String(length=120), nullable=False),
        sa.Column("severity", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("payload", json_type, nullable=False, server_default=json_default),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "ops_retry_queue",
        sa.Column("id", sa.String(length=120), primary_key=True),
        sa.Column("target_type", sa.String(length=80), nullable=False),
        sa.Column("target_id", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payload", json_type, nullable=False, server_default=json_default),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "metrics_snapshots",
        sa.Column("id", sa.String(length=120), primary_key=True),
        sa.Column("metric_scope", sa.String(length=120), nullable=False),
        sa.Column("payload", json_type, nullable=False, server_default=json_default),
        sa.Column("captured_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    raise RuntimeError("Downgrade is intentionally disabled for S1 workflow ops contracts.")
