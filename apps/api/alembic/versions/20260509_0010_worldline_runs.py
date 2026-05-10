"""s6 worldline runs schema

Revision ID: 20260509_0010
Revises: 20260509_0009
Create Date: 2026-05-09
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260509_0010"
down_revision = "20260509_0009"
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
        "worldline_runs",
        sa.Column("id", sa.String(length=120), primary_key=True),
        sa.Column("tenant_id", sa.String(length=80), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("case_id", sa.String(length=80), sa.ForeignKey("cases.id"), nullable=False),
        sa.Column("world_state_id", sa.String(length=100), sa.ForeignKey("world_states.id"), nullable=False),
        sa.Column("status", sa.String(length=60), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("current_step", sa.String(length=120), nullable=True),
        sa.Column("error_code", sa.String(length=120), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("is_retryable", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("payload", json_type, nullable=False, server_default=json_default),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_worldline_runs_tenant_id", "worldline_runs", ["tenant_id"])
    op.create_index("ix_worldline_runs_case_id", "worldline_runs", ["case_id"])
    op.create_index("ix_worldline_runs_world_state_id", "worldline_runs", ["world_state_id"])

    with op.batch_alter_table("worldline_nodes") as batch_op:
        batch_op.add_column(
            sa.Column(
                "tenant_id",
                sa.String(length=80),
                sa.ForeignKey("tenants.id", name="fk_worldline_nodes_tenant_id_tenants"),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "worldline_run_id",
                sa.String(length=120),
                sa.ForeignKey("worldline_runs.id", name="fk_worldline_nodes_worldline_run_id_worldline_runs"),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "world_state_id",
                sa.String(length=100),
                sa.ForeignKey("world_states.id", name="fk_worldline_nodes_world_state_id_world_states"),
                nullable=True,
            )
        )
        batch_op.add_column(sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
        batch_op.add_column(sa.Column("evidence_refs", json_type, nullable=False, server_default=list_default))
    op.create_index("ix_worldline_nodes_tenant_id", "worldline_nodes", ["tenant_id"])
    op.create_index("ix_worldline_nodes_worldline_run_id", "worldline_nodes", ["worldline_run_id"])
    op.create_index("ix_worldline_nodes_world_state_id", "worldline_nodes", ["world_state_id"])

    op.create_table(
        "worldline_edges",
        sa.Column("id", sa.String(length=120), primary_key=True),
        sa.Column("tenant_id", sa.String(length=80), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("worldline_run_id", sa.String(length=120), sa.ForeignKey("worldline_runs.id"), nullable=False),
        sa.Column("from_node_id", sa.String(length=100), sa.ForeignKey("worldline_nodes.id"), nullable=False),
        sa.Column("to_node_id", sa.String(length=100), sa.ForeignKey("worldline_nodes.id"), nullable=False),
        sa.Column("probability_delta", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("payload", json_type, nullable=False, server_default=json_default),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_worldline_edges_worldline_run_id", "worldline_edges", ["worldline_run_id"])

    op.create_table(
        "worldline_interventions",
        sa.Column("id", sa.String(length=120), primary_key=True),
        sa.Column("tenant_id", sa.String(length=80), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("worldline_run_id", sa.String(length=120), sa.ForeignKey("worldline_runs.id"), nullable=False),
        sa.Column("action", sa.String(length=160), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("constraints", json_type, nullable=False, server_default=json_default),
        sa.Column("payload", json_type, nullable=False, server_default=json_default),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_worldline_interventions_worldline_run_id", "worldline_interventions", ["worldline_run_id"])


def downgrade() -> None:
    raise RuntimeError("Downgrade is intentionally disabled for S6 worldline run schema.")
