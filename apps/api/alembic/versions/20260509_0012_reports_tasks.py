"""s7a reports tasks schema

Revision ID: 20260509_0012
Revises: 20260509_0011
Create Date: 2026-05-09
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260509_0012"
down_revision = "20260509_0011"
branch_labels = None
depends_on = None


def _json_type():
    return sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def _json_default(bind):
    return sa.text("'{}'::jsonb") if bind.dialect.name == "postgresql" else sa.text("'{}'")


def _list_default(bind):
    return sa.text("'[]'::jsonb") if bind.dialect.name == "postgresql" else sa.text("'[]'")


def _column_exists(bind, table: str, column: str) -> bool:
    inspector = sa.inspect(bind)
    return column in {row["name"] for row in inspector.get_columns(table)}


def _index_exists(bind, table: str, index: str) -> bool:
    inspector = sa.inspect(bind)
    return index in {row["name"] for row in inspector.get_indexes(table)}


def upgrade() -> None:
    bind = op.get_bind()
    json_type = _json_type()
    json_default = _json_default(bind)
    list_default = _list_default(bind)

    report_columns = [
        (
            "tenant_id",
            sa.Column(
                "tenant_id",
                sa.String(length=80),
                sa.ForeignKey("tenants.id", name="fk_reports_tenant_id_tenants"),
                nullable=True,
            ),
        ),
        (
            "topic_id",
            sa.Column(
                "topic_id",
                sa.String(length=120),
                sa.ForeignKey("topics.id", name="fk_reports_topic_id_topics"),
                nullable=True,
            ),
        ),
        ("current_version", sa.Column("current_version", sa.Integer(), nullable=False, server_default="1")),
        (
            "review_id",
            sa.Column(
                "review_id",
                sa.String(length=120),
                sa.ForeignKey("reviews.id", name="fk_reports_review_id_reviews"),
                nullable=True,
            ),
        ),
        ("published_at", sa.Column("published_at", sa.DateTime(timezone=True), nullable=True)),
        ("exported_at", sa.Column("exported_at", sa.DateTime(timezone=True), nullable=True)),
    ]
    missing_report_columns = [column for name, column in report_columns if not _column_exists(bind, "reports", name)]
    if missing_report_columns:
        with op.batch_alter_table("reports") as batch_op:
            for column in missing_report_columns:
                batch_op.add_column(column)
    if not _index_exists(bind, "reports", "ix_reports_tenant_id"):
        op.create_index("ix_reports_tenant_id", "reports", ["tenant_id"])
    if not _index_exists(bind, "reports", "ix_reports_topic_id"):
        op.create_index("ix_reports_topic_id", "reports", ["topic_id"])

    op.create_table(
        "report_versions",
        sa.Column("id", sa.String(length=120), primary_key=True),
        sa.Column("tenant_id", sa.String(length=80), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("report_id", sa.String(length=100), sa.ForeignKey("reports.id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=60), nullable=False),
        sa.Column("sections", json_type, nullable=False, server_default=list_default),
        sa.Column("diff", json_type, nullable=False, server_default=json_default),
        sa.Column("payload", json_type, nullable=False, server_default=json_default),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_report_versions_tenant_id", "report_versions", ["tenant_id"])
    op.create_index("ix_report_versions_report_id", "report_versions", ["report_id"])

    op.create_table(
        "report_claims",
        sa.Column("id", sa.String(length=120), primary_key=True),
        sa.Column("tenant_id", sa.String(length=80), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("report_id", sa.String(length=100), sa.ForeignKey("reports.id"), nullable=False),
        sa.Column("report_version_id", sa.String(length=120), sa.ForeignKey("report_versions.id"), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("claim_type", sa.String(length=80), nullable=False),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=60), nullable=False),
        sa.Column("validation_status", sa.String(length=60), nullable=False),
        sa.Column("source_object_type", sa.String(length=80), nullable=False),
        sa.Column("source_object_id", sa.String(length=120), nullable=False),
        sa.Column("evidence_refs", json_type, nullable=False, server_default=list_default),
        sa.Column("payload", json_type, nullable=False, server_default=json_default),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_report_claims_tenant_id", "report_claims", ["tenant_id"])
    op.create_index("ix_report_claims_report_id", "report_claims", ["report_id"])
    op.create_index("ix_report_claims_report_version_id", "report_claims", ["report_version_id"])

    op.create_table(
        "report_exports",
        sa.Column("id", sa.String(length=120), primary_key=True),
        sa.Column("tenant_id", sa.String(length=80), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("report_id", sa.String(length=100), sa.ForeignKey("reports.id"), nullable=False),
        sa.Column("format", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=60), nullable=False),
        sa.Column("file_uri", sa.String(length=500), nullable=True),
        sa.Column("watermark", sa.String(length=120), nullable=False),
        sa.Column("content_hash", sa.String(length=128), nullable=True),
        sa.Column("payload", json_type, nullable=False, server_default=json_default),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_report_exports_tenant_id", "report_exports", ["tenant_id"])
    op.create_index("ix_report_exports_report_id", "report_exports", ["report_id"])

    task_columns = [
        (
            "tenant_id",
            sa.Column(
                "tenant_id",
                sa.String(length=80),
                sa.ForeignKey("tenants.id", name="fk_tasks_tenant_id_tenants"),
                nullable=True,
            ),
        ),
        (
            "report_id",
            sa.Column(
                "report_id",
                sa.String(length=100),
                sa.ForeignKey("reports.id", name="fk_tasks_report_id_reports"),
                nullable=True,
            ),
        ),
        ("due_at", sa.Column("due_at", sa.DateTime(timezone=True), nullable=True)),
        ("version", sa.Column("version", sa.Integer(), nullable=False, server_default="1")),
        ("evidence_refs", sa.Column("evidence_refs", json_type, nullable=False, server_default=list_default)),
    ]
    missing_task_columns = [column for name, column in task_columns if not _column_exists(bind, "tasks", name)]
    if missing_task_columns:
        with op.batch_alter_table("tasks") as batch_op:
            for column in missing_task_columns:
                batch_op.add_column(column)
    if not _index_exists(bind, "tasks", "ix_tasks_tenant_id"):
        op.create_index("ix_tasks_tenant_id", "tasks", ["tenant_id"])
    if not _index_exists(bind, "tasks", "ix_tasks_report_id"):
        op.create_index("ix_tasks_report_id", "tasks", ["report_id"])

    op.create_table(
        "task_events",
        sa.Column("id", sa.String(length=120), primary_key=True),
        sa.Column("tenant_id", sa.String(length=80), sa.ForeignKey("tenants.id"), nullable=True),
        sa.Column("task_id", sa.String(length=100), sa.ForeignKey("tasks.id"), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("from_status", sa.String(length=60), nullable=True),
        sa.Column("to_status", sa.String(length=60), nullable=True),
        sa.Column("actor_id", sa.String(length=120), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("payload", json_type, nullable=False, server_default=json_default),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_task_events_task_id", "task_events", ["task_id"])


def downgrade() -> None:
    raise RuntimeError("Downgrade is intentionally disabled for S7A reports/tasks schema.")
