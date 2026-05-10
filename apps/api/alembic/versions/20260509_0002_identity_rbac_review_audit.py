"""s1 foundation identity rbac review ops schema

Revision ID: 20260509_0002
Revises: 20260508_0001
Create Date: 2026-05-09
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260509_0002"
down_revision = "20260508_0001"
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

    op.create_table(
        "tenants",
        sa.Column("id", sa.String(length=80), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="active"),
        sa.Column("payload", json_type, nullable=False, server_default=json_default),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "users",
        sa.Column("id", sa.String(length=100), primary_key=True),
        sa.Column("tenant_id", sa.String(length=80), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("username", sa.String(length=120), nullable=False, unique=True),
        sa.Column("display_name", sa.String(length=160), nullable=False),
        sa.Column("password_hash", sa.String(length=260), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="active"),
        sa.Column("failed_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payload", json_type, nullable=False, server_default=json_default),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_users_tenant_id", "users", ["tenant_id"])

    op.create_table(
        "roles",
        sa.Column("id", sa.String(length=100), primary_key=True),
        sa.Column("tenant_id", sa.String(length=80), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.String(length=240), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="active"),
        sa.Column("payload", json_type, nullable=False, server_default=json_default),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_roles_tenant_id", "roles", ["tenant_id"])

    op.create_table(
        "permissions",
        sa.Column("id", sa.String(length=120), primary_key=True),
        sa.Column("code", sa.String(length=120), nullable=False, unique=True),
        sa.Column("description", sa.String(length=240), nullable=False),
        sa.Column("payload", json_type, nullable=False, server_default=json_default),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "user_roles",
        sa.Column("user_id", sa.String(length=100), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("role_id", sa.String(length=100), sa.ForeignKey("roles.id"), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "role_permissions",
        sa.Column("role_id", sa.String(length=100), sa.ForeignKey("roles.id"), primary_key=True),
        sa.Column("permission_id", sa.String(length=120), sa.ForeignKey("permissions.id"), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "sessions",
        sa.Column("id", sa.String(length=120), primary_key=True),
        sa.Column("tenant_id", sa.String(length=80), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("user_id", sa.String(length=100), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("access_token_hash", sa.String(length=128), nullable=False, unique=True),
        sa.Column("refresh_token_hash", sa.String(length=128), nullable=False, unique=True),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="active"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", json_type, nullable=False, server_default=json_default),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_sessions_tenant_id", "sessions", ["tenant_id"])
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"])

    op.create_table(
        "review_templates",
        sa.Column("id", sa.String(length=100), primary_key=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("object_type", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="active"),
        sa.Column("payload", json_type, nullable=False, server_default=json_default),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "reviews",
        sa.Column("id", sa.String(length=120), primary_key=True),
        sa.Column("tenant_id", sa.String(length=80), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("template_id", sa.String(length=100), sa.ForeignKey("review_templates.id"), nullable=False),
        sa.Column("object_type", sa.String(length=80), nullable=False),
        sa.Column("object_id", sa.String(length=200), nullable=False),
        sa.Column("object_version", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("reviewer_id", sa.String(length=100), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("blocker_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("waived_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("waiver_reason", sa.Text(), nullable=True),
        sa.Column("payload", json_type, nullable=False, server_default=json_default),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_reviews_tenant_id", "reviews", ["tenant_id"])
    op.create_index("ix_reviews_template_id", "reviews", ["template_id"])

    op.create_table(
        "review_results",
        sa.Column("id", sa.String(length=120), primary_key=True),
        sa.Column("review_id", sa.String(length=120), sa.ForeignKey("reviews.id"), nullable=False),
        sa.Column("reviewer_id", sa.String(length=100), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("findings", json_type, nullable=False, server_default=sa.text("'[]'::jsonb") if bind.dialect.name == "postgresql" else sa.text("'[]'")),
        sa.Column("blockers", json_type, nullable=False, server_default=sa.text("'[]'::jsonb") if bind.dialect.name == "postgresql" else sa.text("'[]'")),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("payload", json_type, nullable=False, server_default=json_default),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_review_results_review_id", "review_results", ["review_id"])

    with op.batch_alter_table("audit_logs") as batch:
        batch.alter_column("case_id", existing_type=sa.String(length=80), nullable=True)
        batch.add_column(sa.Column("tenant_id", sa.String(length=80), nullable=True))
        batch.add_column(sa.Column("actor_id", sa.String(length=120), nullable=True))
        batch.add_column(sa.Column("object_version", sa.String(length=80), nullable=True))
        batch.add_column(sa.Column("before", json_type, nullable=False, server_default=json_default))
        batch.add_column(sa.Column("after", json_type, nullable=False, server_default=json_default))
        batch.add_column(sa.Column("diff", json_type, nullable=False, server_default=json_default))
        batch.add_column(sa.Column("trace_id", sa.String(length=120), nullable=True))
        batch.add_column(sa.Column("ip_address", sa.String(length=80), nullable=True))
        batch.add_column(sa.Column("user_agent", sa.String(length=240), nullable=True))
    op.create_index("ix_audit_logs_tenant_id", "audit_logs", ["tenant_id"])


def downgrade() -> None:
    raise RuntimeError("Downgrade is intentionally disabled for S1 foundation: use forward-only migrations.")
