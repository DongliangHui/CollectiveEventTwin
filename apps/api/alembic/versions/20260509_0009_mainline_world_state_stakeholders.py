"""s5 mainline world state stakeholders schema

Revision ID: 20260509_0009
Revises: 20260509_0008
Create Date: 2026-05-09
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260509_0009"
down_revision = "20260509_0008"
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
        "mainline_versions",
        sa.Column("id", sa.String(length=120), primary_key=True),
        sa.Column("tenant_id", sa.String(length=80), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("mainline_id", sa.String(length=100), sa.ForeignKey("mainlines.id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=60), nullable=False),
        sa.Column("diff", json_type, nullable=False, server_default=json_default),
        sa.Column("payload", json_type, nullable=False, server_default=json_default),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_mainline_versions_tenant_id", "mainline_versions", ["tenant_id"])
    op.create_index("ix_mainline_versions_mainline_id", "mainline_versions", ["mainline_id"])
    op.create_index("ux_mainline_versions_mainline_version", "mainline_versions", ["mainline_id", "version"], unique=True)

    op.create_table(
        "mainline_nodes",
        sa.Column("id", sa.String(length=120), primary_key=True),
        sa.Column("tenant_id", sa.String(length=80), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("mainline_id", sa.String(length=100), sa.ForeignKey("mainlines.id"), nullable=False),
        sa.Column("node_type", sa.String(length=80), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=60), nullable=False),
        sa.Column("evidence_refs", json_type, nullable=False, server_default=list_default),
        sa.Column("payload", json_type, nullable=False, server_default=json_default),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_mainline_nodes_tenant_id", "mainline_nodes", ["tenant_id"])
    op.create_index("ix_mainline_nodes_mainline_id", "mainline_nodes", ["mainline_id"])
    op.create_index("ix_mainline_nodes_type", "mainline_nodes", ["node_type"])

    op.create_table(
        "case_graph_nodes",
        sa.Column("id", sa.String(length=120), primary_key=True),
        sa.Column("tenant_id", sa.String(length=80), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("case_id", sa.String(length=80), sa.ForeignKey("cases.id"), nullable=False),
        sa.Column("topic_id", sa.String(length=120), sa.ForeignKey("topics.id"), nullable=True),
        sa.Column("mainline_id", sa.String(length=100), sa.ForeignKey("mainlines.id"), nullable=False),
        sa.Column("world_state_id", sa.String(length=100), sa.ForeignKey("world_states.id"), nullable=True),
        sa.Column("node_type", sa.String(length=80), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("status", sa.String(length=60), nullable=False),
        sa.Column("evidence_refs", json_type, nullable=False, server_default=list_default),
        sa.Column("payload", json_type, nullable=False, server_default=json_default),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_case_graph_nodes_tenant_id", "case_graph_nodes", ["tenant_id"])
    op.create_index("ix_case_graph_nodes_case_id", "case_graph_nodes", ["case_id"])
    op.create_index("ix_case_graph_nodes_topic_id", "case_graph_nodes", ["topic_id"])
    op.create_index("ix_case_graph_nodes_mainline_id", "case_graph_nodes", ["mainline_id"])
    op.create_index("ix_case_graph_nodes_world_state_id", "case_graph_nodes", ["world_state_id"])

    op.create_table(
        "stakeholders",
        sa.Column("id", sa.String(length=120), primary_key=True),
        sa.Column("tenant_id", sa.String(length=80), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("case_id", sa.String(length=80), sa.ForeignKey("cases.id"), nullable=False),
        sa.Column("topic_id", sa.String(length=120), sa.ForeignKey("topics.id"), nullable=True),
        sa.Column("mainline_id", sa.String(length=100), sa.ForeignKey("mainlines.id"), nullable=False),
        sa.Column("graph_node_id", sa.String(length=120), sa.ForeignKey("case_graph_nodes.id"), nullable=True),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("role", sa.String(length=120), nullable=False),
        sa.Column("stance", sa.String(length=240), nullable=False),
        sa.Column("status", sa.String(length=60), nullable=False),
        sa.Column("reviewer_id", sa.String(length=100), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("evidence_refs", json_type, nullable=False, server_default=list_default),
        sa.Column("payload", json_type, nullable=False, server_default=json_default),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_stakeholders_tenant_id", "stakeholders", ["tenant_id"])
    op.create_index("ix_stakeholders_case_id", "stakeholders", ["case_id"])
    op.create_index("ix_stakeholders_topic_id", "stakeholders", ["topic_id"])
    op.create_index("ix_stakeholders_mainline_id", "stakeholders", ["mainline_id"])
    op.create_index("ix_stakeholders_graph_node_id", "stakeholders", ["graph_node_id"])


def downgrade() -> None:
    raise RuntimeError("Downgrade is intentionally disabled for S5 mainline/world-state/stakeholder schema.")
