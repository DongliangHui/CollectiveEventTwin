"""p0 core schema

Revision ID: 20260508_0001
Revises:
Create Date: 2026-05-08
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260508_0001"
down_revision = None
branch_labels = None
depends_on = None


def _json_type():
    return sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def _json_default(bind):
    if bind.dialect.name == "postgresql":
        return sa.text("'{}'::jsonb")
    return sa.text("'{}'")


def _bool_false(bind):
    if bind.dialect.name == "postgresql":
        return sa.text("false")
    return sa.text("0")


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    json_type = _json_type()
    json_default = _json_default(bind)
    bool_false = _bool_false(bind)

    op.create_table(
        "cases",
        sa.Column("id", sa.String(length=80), primary_key=True),
        sa.Column("slug", sa.String(length=160), nullable=False, unique=True),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("scenario_type", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="active"),
        sa.Column("payload", json_type, nullable=False, server_default=json_default),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    common = [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]

    op.create_table(
        "source_records",
        sa.Column("id", sa.String(length=100), primary_key=True),
        sa.Column("case_id", sa.String(length=80), sa.ForeignKey("cases.id"), nullable=False, index=True),
        sa.Column("source_id", sa.String(length=100), nullable=False),
        sa.Column("source_name", sa.String(length=200), nullable=False),
        sa.Column("access_mode", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("trust", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("accepted", sa.Boolean(), nullable=False, server_default=bool_false),
        sa.Column("blocked_reason", sa.String(length=160), nullable=True),
        sa.Column("payload", json_type, nullable=False, server_default=json_default),
        *common,
    )

    op.create_table(
        "signals",
        sa.Column("id", sa.String(length=100), primary_key=True),
        sa.Column("case_id", sa.String(length=80), sa.ForeignKey("cases.id"), nullable=False, index=True),
        sa.Column("mainline_id", sa.String(length=100), nullable=True, index=True),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("priority", sa.String(length=20), nullable=False),
        sa.Column("region_id", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=60), nullable=False),
        sa.Column("scores", json_type, nullable=False, server_default=json_default),
        sa.Column("payload", json_type, nullable=False, server_default=json_default),
        *common,
    )

    op.create_table(
        "evidence",
        sa.Column("id", sa.String(length=100), primary_key=True),
        sa.Column("case_id", sa.String(length=80), sa.ForeignKey("cases.id"), nullable=False, index=True),
        sa.Column("signal_id", sa.String(length=100), sa.ForeignKey("signals.id"), nullable=True, index=True),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("excerpt", sa.Text(), nullable=False),
        sa.Column("masked_excerpt", sa.Text(), nullable=False),
        sa.Column("source", sa.String(length=200), nullable=False),
        sa.Column("credibility", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=60), nullable=False),
        sa.Column("sensitivity", sa.String(length=80), nullable=False),
        sa.Column("payload", json_type, nullable=False, server_default=json_default),
        *common,
    )

    for table, extra in [
        ("risk_factors", [sa.Column("name", sa.String(length=160), nullable=False), sa.Column("category", sa.String(length=80), nullable=False), sa.Column("confidence", sa.Float(), nullable=False)]),
        ("mainlines", [sa.Column("title", sa.String(length=240), nullable=False), sa.Column("confidence", sa.Float(), nullable=False, server_default="0")]),
        ("world_states", [sa.Column("title", sa.String(length=240), nullable=False)]),
        ("worldline_nodes", [sa.Column("title", sa.String(length=240), nullable=False), sa.Column("branch", sa.String(length=40), nullable=False), sa.Column("probability", sa.Integer(), nullable=False), sa.Column("risk", sa.Integer(), nullable=False)]),
        ("council_sessions", [sa.Column("node_id", sa.String(length=100), nullable=False), sa.Column("hypothesis", sa.Text(), nullable=False)]),
        ("reports", [sa.Column("title", sa.String(length=240), nullable=False), sa.Column("human_confirmed", sa.Boolean(), nullable=False, server_default=bool_false)]),
        ("tasks", [sa.Column("title", sa.String(length=240), nullable=False), sa.Column("owner", sa.String(length=120), nullable=False), sa.Column("due_label", sa.String(length=80), nullable=False)]),
        ("workflow_runs", [sa.Column("workflow_name", sa.String(length=120), nullable=False), sa.Column("workflow_id", sa.String(length=160), nullable=False)]),
    ]:
        op.create_table(
            table,
            sa.Column("id", sa.String(length=100), primary_key=True),
            sa.Column("case_id", sa.String(length=80), sa.ForeignKey("cases.id"), nullable=False, index=True),
            *extra,
            sa.Column("status", sa.String(length=60), nullable=False),
            sa.Column("payload", json_type, nullable=False, server_default=json_default),
            *common,
        )

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.String(length=120), primary_key=True),
        sa.Column("case_id", sa.String(length=80), sa.ForeignKey("cases.id"), nullable=False, index=True),
        sa.Column("actor", sa.String(length=120), nullable=False),
        sa.Column("action", sa.String(length=120), nullable=False),
        sa.Column("object_type", sa.String(length=80), nullable=False),
        sa.Column("object_id", sa.String(length=120), nullable=False),
        sa.Column("reason", sa.String(length=240), nullable=True),
        sa.Column("payload", json_type, nullable=False, server_default=json_default),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    raise RuntimeError("Downgrade is intentionally disabled for P0: no destructive schema action.")
