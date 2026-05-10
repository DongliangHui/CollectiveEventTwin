"""s6 llm agent council schema

Revision ID: 20260509_0011
Revises: 20260509_0010
Create Date: 2026-05-09
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260509_0011"
down_revision = "20260509_0010"
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
        "llm_providers",
        sa.Column("id", sa.String(length=120), primary_key=True),
        sa.Column("tenant_id", sa.String(length=80), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=60), nullable=False),
        sa.Column("model_defaults", json_type, nullable=False, server_default=json_default),
        sa.Column("payload", json_type, nullable=False, server_default=json_default),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_llm_providers_tenant_id", "llm_providers", ["tenant_id"])

    op.create_table(
        "prompt_templates",
        sa.Column("id", sa.String(length=120), primary_key=True),
        sa.Column("tenant_id", sa.String(length=80), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("version", sa.String(length=80), nullable=False),
        sa.Column("schema_version", sa.String(length=80), nullable=False),
        sa.Column("template", sa.Text(), nullable=False),
        sa.Column("payload", json_type, nullable=False, server_default=json_default),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_prompt_templates_tenant_id", "prompt_templates", ["tenant_id"])

    op.create_table(
        "agent_templates",
        sa.Column("id", sa.String(length=120), primary_key=True),
        sa.Column("tenant_id", sa.String(length=80), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("version", sa.String(length=80), nullable=False),
        sa.Column("payload", json_type, nullable=False, server_default=json_default),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_agent_templates_tenant_id", "agent_templates", ["tenant_id"])

    op.create_table(
        "llm_calls",
        sa.Column("id", sa.String(length=120), primary_key=True),
        sa.Column("tenant_id", sa.String(length=80), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("provider_id", sa.String(length=120), sa.ForeignKey("llm_providers.id"), nullable=False),
        sa.Column("prompt_template_id", sa.String(length=120), sa.ForeignKey("prompt_templates.id"), nullable=True),
        sa.Column("object_type", sa.String(length=80), nullable=False),
        sa.Column("object_id", sa.String(length=120), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=False),
        sa.Column("prompt_version", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=60), nullable=False),
        sa.Column("tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cost", sa.Float(), nullable=False, server_default="0"),
        sa.Column("latency_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("input_refs", json_type, nullable=False, server_default=list_default),
        sa.Column("output", json_type, nullable=False, server_default=json_default),
        sa.Column("payload", json_type, nullable=False, server_default=json_default),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_llm_calls_provider_id", "llm_calls", ["provider_id"])
    op.create_index("ix_llm_calls_prompt_template_id", "llm_calls", ["prompt_template_id"])
    op.create_index("ix_llm_calls_object_id", "llm_calls", ["object_id"])

    op.create_table(
        "agent_profiles",
        sa.Column("id", sa.String(length=120), primary_key=True),
        sa.Column("tenant_id", sa.String(length=80), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("stakeholder_id", sa.String(length=120), sa.ForeignKey("stakeholders.id"), nullable=False),
        sa.Column("worldline_run_id", sa.String(length=120), sa.ForeignKey("worldline_runs.id"), nullable=False),
        sa.Column("status", sa.String(length=60), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("files", json_type, nullable=False, server_default=json_default),
        sa.Column("evidence_refs", json_type, nullable=False, server_default=list_default),
        sa.Column("payload", json_type, nullable=False, server_default=json_default),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_agent_profiles_stakeholder_id", "agent_profiles", ["stakeholder_id"])
    op.create_index("ix_agent_profiles_worldline_run_id", "agent_profiles", ["worldline_run_id"])

    op.create_table(
        "agent_profile_files",
        sa.Column("id", sa.String(length=120), primary_key=True),
        sa.Column("tenant_id", sa.String(length=80), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("agent_profile_id", sa.String(length=120), sa.ForeignKey("agent_profiles.id"), nullable=False),
        sa.Column("file_type", sa.String(length=40), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("payload", json_type, nullable=False, server_default=json_default),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_agent_profile_files_agent_profile_id", "agent_profile_files", ["agent_profile_id"])

    op.create_table(
        "council_messages",
        sa.Column("id", sa.String(length=120), primary_key=True),
        sa.Column("tenant_id", sa.String(length=80), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("council_session_id", sa.String(length=100), sa.ForeignKey("council_sessions.id"), nullable=False),
        sa.Column("agent_profile_id", sa.String(length=120), sa.ForeignKey("agent_profiles.id"), nullable=True),
        sa.Column("role", sa.String(length=120), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("evidence_refs", json_type, nullable=False, server_default=list_default),
        sa.Column("payload", json_type, nullable=False, server_default=json_default),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_council_messages_council_session_id", "council_messages", ["council_session_id"])

    op.create_table(
        "council_results",
        sa.Column("id", sa.String(length=120), primary_key=True),
        sa.Column("tenant_id", sa.String(length=80), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("council_session_id", sa.String(length=100), sa.ForeignKey("council_sessions.id"), nullable=False),
        sa.Column("worldline_run_id", sa.String(length=120), sa.ForeignKey("worldline_runs.id"), nullable=False),
        sa.Column("status", sa.String(length=60), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("evidence_refs", json_type, nullable=False, server_default=list_default),
        sa.Column("payload", json_type, nullable=False, server_default=json_default),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_council_results_council_session_id", "council_results", ["council_session_id"])
    op.create_index("ix_council_results_worldline_run_id", "council_results", ["worldline_run_id"])

    op.create_table(
        "blocked_claims",
        sa.Column("id", sa.String(length=120), primary_key=True),
        sa.Column("tenant_id", sa.String(length=80), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("claim", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("source_ref", json_type, nullable=False, server_default=json_default),
        sa.Column("llm_call_id", sa.String(length=120), sa.ForeignKey("llm_calls.id"), nullable=True),
        sa.Column("council_result_id", sa.String(length=120), sa.ForeignKey("council_results.id"), nullable=True),
        sa.Column("payload", json_type, nullable=False, server_default=json_default),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_blocked_claims_llm_call_id", "blocked_claims", ["llm_call_id"])
    op.create_index("ix_blocked_claims_council_result_id", "blocked_claims", ["council_result_id"])


def downgrade() -> None:
    raise RuntimeError("Downgrade is intentionally disabled for S6 LLM/agent/council schema.")
