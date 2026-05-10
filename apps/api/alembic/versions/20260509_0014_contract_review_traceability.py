"""s1 contract review traceability schema

Revision ID: 20260509_0014
Revises: 20260509_0013
Create Date: 2026-05-09
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260509_0014"
down_revision = "20260509_0013"
branch_labels = None
depends_on = None


def _json_type():
    return sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def _json_default(bind):
    return sa.text("'{}'::jsonb") if bind.dialect.name == "postgresql" else sa.text("'{}'")


def _list_default(bind):
    return sa.text("'[]'::jsonb") if bind.dialect.name == "postgresql" else sa.text("'[]'")


def _timestamps():
    return (
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def upgrade() -> None:
    bind = op.get_bind()
    json_type = _json_type()
    json_default = _json_default(bind)
    list_default = _list_default(bind)

    op.create_table(
        "review_checklist_versions",
        sa.Column("id", sa.String(length=120), primary_key=True),
        sa.Column("tenant_id", sa.String(length=80), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("artifact_type", sa.String(length=80), nullable=False),
        sa.Column("version", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=60), nullable=False),
        sa.Column("checklist_schema", json_type, nullable=False, server_default=json_default),
        sa.Column("items", json_type, nullable=False, server_default=list_default),
        sa.Column("published_by_id", sa.String(length=100), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payload", json_type, nullable=False, server_default=json_default),
        *_timestamps(),
    )
    op.create_index("ix_review_checklist_versions_tenant_id", "review_checklist_versions", ["tenant_id"])
    op.create_index("ix_review_checklist_versions_artifact_type", "review_checklist_versions", ["artifact_type"])
    op.create_index("ix_review_checklist_versions_status", "review_checklist_versions", ["status"])
    op.create_index("ix_review_checklist_versions_created_at", "review_checklist_versions", ["created_at"])

    op.create_table(
        "review_gate_records",
        sa.Column("id", sa.String(length=120), primary_key=True),
        sa.Column("tenant_id", sa.String(length=80), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("case_id", sa.String(length=80), sa.ForeignKey("cases.id"), nullable=True),
        sa.Column("review_id", sa.String(length=120), sa.ForeignKey("reviews.id"), nullable=True),
        sa.Column("task_id", sa.String(length=100), sa.ForeignKey("tasks.id"), nullable=False),
        sa.Column(
            "checklist_version_id",
            sa.String(length=120),
            sa.ForeignKey("review_checklist_versions.id"),
            nullable=True,
        ),
        sa.Column("artifact_type", sa.String(length=80), nullable=False),
        sa.Column("artifact_id", sa.String(length=200), nullable=False),
        sa.Column("artifact_version", sa.String(length=80), nullable=True),
        sa.Column("gate_code", sa.String(length=120), nullable=True),
        sa.Column("reviewer_id", sa.String(length=100), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("implemented_by_id", sa.String(length=100), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("result", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=60), nullable=False),
        sa.Column("findings", json_type, nullable=False, server_default=list_default),
        sa.Column("blockers", json_type, nullable=False, server_default=list_default),
        sa.Column("evidence_refs", json_type, nullable=False, server_default=list_default),
        sa.Column("audit_log_id", sa.String(length=120), sa.ForeignKey("audit_logs.id"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payload", json_type, nullable=False, server_default=json_default),
        *_timestamps(),
    )
    op.create_index("ix_review_gate_records_tenant_id", "review_gate_records", ["tenant_id"])
    op.create_index("ix_review_gate_records_case_id", "review_gate_records", ["case_id"])
    op.create_index("ix_review_gate_records_review_id", "review_gate_records", ["review_id"])
    op.create_index("ix_review_gate_records_task_id", "review_gate_records", ["task_id"])
    op.create_index("ix_review_gate_records_checklist_version_id", "review_gate_records", ["checklist_version_id"])
    op.create_index("ix_review_gate_records_reviewer_id", "review_gate_records", ["reviewer_id"])
    op.create_index("ix_review_gate_records_status", "review_gate_records", ["status"])
    op.create_index("ix_review_gate_records_artifact_ref", "review_gate_records", ["artifact_type", "artifact_id"])
    op.create_index("ix_review_gate_records_created_at", "review_gate_records", ["created_at"])

    op.create_table(
        "page_surface_contracts",
        sa.Column("id", sa.String(length=120), primary_key=True),
        sa.Column("tenant_id", sa.String(length=80), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("case_id", sa.String(length=80), sa.ForeignKey("cases.id"), nullable=True),
        sa.Column("surface_id", sa.String(length=160), nullable=False),
        sa.Column("route", sa.String(length=240), nullable=False),
        sa.Column("page_key", sa.String(length=80), nullable=False),
        sa.Column("surface_type", sa.String(length=80), nullable=False),
        sa.Column("parent_surface_id", sa.String(length=160), nullable=True),
        sa.Column("business_domain", sa.String(length=120), nullable=True),
        sa.Column("object_type", sa.String(length=80), nullable=True),
        sa.Column("object_id", sa.String(length=120), nullable=True),
        sa.Column("status", sa.String(length=60), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("state_matrix", json_type, nullable=False, server_default=list_default),
        sa.Column("api_refs", json_type, nullable=False, server_default=list_default),
        sa.Column("review_gate_record_id", sa.String(length=120), sa.ForeignKey("review_gate_records.id"), nullable=True),
        sa.Column("payload", json_type, nullable=False, server_default=json_default),
        *_timestamps(),
    )
    op.create_index("ix_page_surface_contracts_tenant_id", "page_surface_contracts", ["tenant_id"])
    op.create_index("ix_page_surface_contracts_case_id", "page_surface_contracts", ["case_id"])
    op.create_index("ix_page_surface_contracts_surface_id", "page_surface_contracts", ["surface_id"])
    op.create_index("ix_page_surface_contracts_status", "page_surface_contracts", ["status"])
    op.create_index("ix_page_surface_contracts_review_gate_record_id", "page_surface_contracts", ["review_gate_record_id"])
    op.create_index("ix_page_surface_contracts_object_ref", "page_surface_contracts", ["object_type", "object_id"])
    op.create_index("ix_page_surface_contracts_created_at", "page_surface_contracts", ["created_at"])

    op.create_table(
        "page_view_states",
        sa.Column("id", sa.String(length=120), primary_key=True),
        sa.Column("tenant_id", sa.String(length=80), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("case_id", sa.String(length=80), sa.ForeignKey("cases.id"), nullable=True),
        sa.Column("surface_contract_id", sa.String(length=120), sa.ForeignKey("page_surface_contracts.id"), nullable=True),
        sa.Column("surface_id", sa.String(length=160), nullable=False),
        sa.Column("route", sa.String(length=240), nullable=False),
        sa.Column("user_id", sa.String(length=100), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("object_type", sa.String(length=80), nullable=True),
        sa.Column("object_id", sa.String(length=120), nullable=True),
        sa.Column("status", sa.String(length=60), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("view_state", json_type, nullable=False, server_default=json_default),
        sa.Column("selected_refs", json_type, nullable=False, server_default=list_default),
        sa.Column("review_gate_record_id", sa.String(length=120), sa.ForeignKey("review_gate_records.id"), nullable=True),
        sa.Column("payload", json_type, nullable=False, server_default=json_default),
        *_timestamps(),
    )
    op.create_index("ix_page_view_states_tenant_id", "page_view_states", ["tenant_id"])
    op.create_index("ix_page_view_states_case_id", "page_view_states", ["case_id"])
    op.create_index("ix_page_view_states_surface_contract_id", "page_view_states", ["surface_contract_id"])
    op.create_index("ix_page_view_states_surface_id", "page_view_states", ["surface_id"])
    op.create_index("ix_page_view_states_user_id", "page_view_states", ["user_id"])
    op.create_index("ix_page_view_states_status", "page_view_states", ["status"])
    op.create_index("ix_page_view_states_review_gate_record_id", "page_view_states", ["review_gate_record_id"])
    op.create_index("ix_page_view_states_object_ref", "page_view_states", ["object_type", "object_id"])
    op.create_index("ix_page_view_states_created_at", "page_view_states", ["created_at"])

    op.create_table(
        "browser_verification_records",
        sa.Column("id", sa.String(length=120), primary_key=True),
        sa.Column("tenant_id", sa.String(length=80), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("case_id", sa.String(length=80), sa.ForeignKey("cases.id"), nullable=True),
        sa.Column("surface_contract_id", sa.String(length=120), sa.ForeignKey("page_surface_contracts.id"), nullable=True),
        sa.Column("surface_id", sa.String(length=160), nullable=False),
        sa.Column("route", sa.String(length=240), nullable=False),
        sa.Column("test_id", sa.String(length=120), nullable=False),
        sa.Column("viewport", sa.String(length=80), nullable=True),
        sa.Column("status", sa.String(length=60), nullable=False),
        sa.Column("result", sa.String(length=60), nullable=False),
        sa.Column("screenshot_uri", sa.String(length=500), nullable=True),
        sa.Column("network_log_refs", json_type, nullable=False, server_default=list_default),
        sa.Column("console_log_refs", json_type, nullable=False, server_default=list_default),
        sa.Column("evidence_refs", json_type, nullable=False, server_default=list_default),
        sa.Column("review_gate_record_id", sa.String(length=120), sa.ForeignKey("review_gate_records.id"), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payload", json_type, nullable=False, server_default=json_default),
        *_timestamps(),
    )
    op.create_index("ix_browser_verification_records_tenant_id", "browser_verification_records", ["tenant_id"])
    op.create_index("ix_browser_verification_records_case_id", "browser_verification_records", ["case_id"])
    op.create_index(
        "ix_browser_verification_records_surface_contract_id", "browser_verification_records", ["surface_contract_id"]
    )
    op.create_index("ix_browser_verification_records_surface_id", "browser_verification_records", ["surface_id"])
    op.create_index("ix_browser_verification_records_status", "browser_verification_records", ["status"])
    op.create_index(
        "ix_browser_verification_records_review_gate_record_id",
        "browser_verification_records",
        ["review_gate_record_id"],
    )
    op.create_index("ix_browser_verification_records_created_at", "browser_verification_records", ["created_at"])

    op.create_table(
        "business_capability_contracts",
        sa.Column("id", sa.String(length=120), primary_key=True),
        sa.Column("tenant_id", sa.String(length=80), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("case_id", sa.String(length=80), sa.ForeignKey("cases.id"), nullable=True),
        sa.Column("capability_code", sa.String(length=120), nullable=False),
        sa.Column("business_domain", sa.String(length=120), nullable=False),
        sa.Column("business_object_type", sa.String(length=80), nullable=False),
        sa.Column("owner", sa.String(length=120), nullable=True),
        sa.Column("status", sa.String(length=60), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("actions", json_type, nullable=False, server_default=list_default),
        sa.Column("input_schema", json_type, nullable=False, server_default=json_default),
        sa.Column("output_schema", json_type, nullable=False, server_default=json_default),
        sa.Column("review_gate_record_id", sa.String(length=120), sa.ForeignKey("review_gate_records.id"), nullable=True),
        sa.Column("payload", json_type, nullable=False, server_default=json_default),
        *_timestamps(),
    )
    op.create_index("ix_business_capability_contracts_tenant_id", "business_capability_contracts", ["tenant_id"])
    op.create_index("ix_business_capability_contracts_case_id", "business_capability_contracts", ["case_id"])
    op.create_index(
        "ix_business_capability_contracts_capability_code", "business_capability_contracts", ["capability_code"]
    )
    op.create_index("ix_business_capability_contracts_status", "business_capability_contracts", ["status"])
    op.create_index(
        "ix_business_capability_contracts_review_gate_record_id",
        "business_capability_contracts",
        ["review_gate_record_id"],
    )
    op.create_index("ix_business_capability_contracts_created_at", "business_capability_contracts", ["created_at"])

    op.create_table(
        "business_state_machines",
        sa.Column("id", sa.String(length=120), primary_key=True),
        sa.Column("tenant_id", sa.String(length=80), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("case_id", sa.String(length=80), sa.ForeignKey("cases.id"), nullable=True),
        sa.Column(
            "capability_contract_id",
            sa.String(length=120),
            sa.ForeignKey("business_capability_contracts.id"),
            nullable=True,
        ),
        sa.Column("object_type", sa.String(length=80), nullable=False),
        sa.Column("initial_state", sa.String(length=60), nullable=False),
        sa.Column("status", sa.String(length=60), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("states", json_type, nullable=False, server_default=list_default),
        sa.Column("transitions", json_type, nullable=False, server_default=list_default),
        sa.Column("terminal_states", json_type, nullable=False, server_default=list_default),
        sa.Column("review_gate_record_id", sa.String(length=120), sa.ForeignKey("review_gate_records.id"), nullable=True),
        sa.Column("payload", json_type, nullable=False, server_default=json_default),
        *_timestamps(),
    )
    op.create_index("ix_business_state_machines_tenant_id", "business_state_machines", ["tenant_id"])
    op.create_index("ix_business_state_machines_case_id", "business_state_machines", ["case_id"])
    op.create_index(
        "ix_business_state_machines_capability_contract_id", "business_state_machines", ["capability_contract_id"]
    )
    op.create_index("ix_business_state_machines_object_type", "business_state_machines", ["object_type"])
    op.create_index("ix_business_state_machines_status", "business_state_machines", ["status"])
    op.create_index(
        "ix_business_state_machines_review_gate_record_id", "business_state_machines", ["review_gate_record_id"]
    )
    op.create_index("ix_business_state_machines_created_at", "business_state_machines", ["created_at"])

    op.create_table(
        "business_flow_edges",
        sa.Column("id", sa.String(length=120), primary_key=True),
        sa.Column("tenant_id", sa.String(length=80), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("case_id", sa.String(length=80), sa.ForeignKey("cases.id"), nullable=True),
        sa.Column(
            "capability_contract_id",
            sa.String(length=120),
            sa.ForeignKey("business_capability_contracts.id"),
            nullable=True,
        ),
        sa.Column("flow_code", sa.String(length=120), nullable=False),
        sa.Column("from_object_type", sa.String(length=80), nullable=False),
        sa.Column("from_object_id", sa.String(length=120), nullable=True),
        sa.Column("to_object_type", sa.String(length=80), nullable=False),
        sa.Column("to_object_id", sa.String(length=120), nullable=True),
        sa.Column("relation", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=60), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("blocker_conditions", json_type, nullable=False, server_default=list_default),
        sa.Column("input_refs", json_type, nullable=False, server_default=list_default),
        sa.Column("output_refs", json_type, nullable=False, server_default=list_default),
        sa.Column("review_gate_record_id", sa.String(length=120), sa.ForeignKey("review_gate_records.id"), nullable=True),
        sa.Column("payload", json_type, nullable=False, server_default=json_default),
        *_timestamps(),
    )
    op.create_index("ix_business_flow_edges_tenant_id", "business_flow_edges", ["tenant_id"])
    op.create_index("ix_business_flow_edges_case_id", "business_flow_edges", ["case_id"])
    op.create_index("ix_business_flow_edges_capability_contract_id", "business_flow_edges", ["capability_contract_id"])
    op.create_index("ix_business_flow_edges_flow_code", "business_flow_edges", ["flow_code"])
    op.create_index("ix_business_flow_edges_status", "business_flow_edges", ["status"])
    op.create_index("ix_business_flow_edges_review_gate_record_id", "business_flow_edges", ["review_gate_record_id"])
    op.create_index("ix_business_flow_edges_from_object_ref", "business_flow_edges", ["from_object_type", "from_object_id"])
    op.create_index("ix_business_flow_edges_to_object_ref", "business_flow_edges", ["to_object_type", "to_object_id"])
    op.create_index("ix_business_flow_edges_created_at", "business_flow_edges", ["created_at"])

    op.create_table(
        "decision_points",
        sa.Column("id", sa.String(length=120), primary_key=True),
        sa.Column("tenant_id", sa.String(length=80), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("case_id", sa.String(length=80), sa.ForeignKey("cases.id"), nullable=True),
        sa.Column(
            "capability_contract_id",
            sa.String(length=120),
            sa.ForeignKey("business_capability_contracts.id"),
            nullable=True,
        ),
        sa.Column("decision_code", sa.String(length=120), nullable=False),
        sa.Column("object_type", sa.String(length=80), nullable=False),
        sa.Column("object_id", sa.String(length=120), nullable=True),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("actor_role", sa.String(length=120), nullable=True),
        sa.Column("required_permission", sa.String(length=120), nullable=True),
        sa.Column("reason_required", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("evidence_required", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("status", sa.String(length=60), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("evidence_refs", json_type, nullable=False, server_default=list_default),
        sa.Column("review_gate_record_id", sa.String(length=120), sa.ForeignKey("review_gate_records.id"), nullable=True),
        sa.Column("audit_log_id", sa.String(length=120), sa.ForeignKey("audit_logs.id"), nullable=True),
        sa.Column("payload", json_type, nullable=False, server_default=json_default),
        *_timestamps(),
    )
    op.create_index("ix_decision_points_tenant_id", "decision_points", ["tenant_id"])
    op.create_index("ix_decision_points_case_id", "decision_points", ["case_id"])
    op.create_index("ix_decision_points_capability_contract_id", "decision_points", ["capability_contract_id"])
    op.create_index("ix_decision_points_decision_code", "decision_points", ["decision_code"])
    op.create_index("ix_decision_points_status", "decision_points", ["status"])
    op.create_index("ix_decision_points_review_gate_record_id", "decision_points", ["review_gate_record_id"])
    op.create_index("ix_decision_points_object_ref", "decision_points", ["object_type", "object_id"])
    op.create_index("ix_decision_points_created_at", "decision_points", ["created_at"])

    op.create_table(
        "write_back_points",
        sa.Column("id", sa.String(length=120), primary_key=True),
        sa.Column("tenant_id", sa.String(length=80), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("case_id", sa.String(length=80), sa.ForeignKey("cases.id"), nullable=True),
        sa.Column(
            "capability_contract_id",
            sa.String(length=120),
            sa.ForeignKey("business_capability_contracts.id"),
            nullable=True,
        ),
        sa.Column("point_code", sa.String(length=120), nullable=False),
        sa.Column("source_object_type", sa.String(length=80), nullable=True),
        sa.Column("source_object_id", sa.String(length=120), nullable=True),
        sa.Column("target_object_type", sa.String(length=80), nullable=False),
        sa.Column("target_object_id", sa.String(length=120), nullable=True),
        sa.Column("target_table", sa.String(length=120), nullable=False),
        sa.Column("version_strategy", sa.String(length=80), nullable=False),
        sa.Column("conflict_strategy", sa.String(length=80), nullable=False),
        sa.Column("rollback_strategy", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=60), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("review_gate_record_id", sa.String(length=120), sa.ForeignKey("review_gate_records.id"), nullable=True),
        sa.Column("audit_log_id", sa.String(length=120), sa.ForeignKey("audit_logs.id"), nullable=True),
        sa.Column("payload", json_type, nullable=False, server_default=json_default),
        *_timestamps(),
    )
    op.create_index("ix_write_back_points_tenant_id", "write_back_points", ["tenant_id"])
    op.create_index("ix_write_back_points_case_id", "write_back_points", ["case_id"])
    op.create_index("ix_write_back_points_capability_contract_id", "write_back_points", ["capability_contract_id"])
    op.create_index("ix_write_back_points_point_code", "write_back_points", ["point_code"])
    op.create_index("ix_write_back_points_status", "write_back_points", ["status"])
    op.create_index("ix_write_back_points_review_gate_record_id", "write_back_points", ["review_gate_record_id"])
    op.create_index(
        "ix_write_back_points_source_object_ref", "write_back_points", ["source_object_type", "source_object_id"]
    )
    op.create_index(
        "ix_write_back_points_target_object_ref", "write_back_points", ["target_object_type", "target_object_id"]
    )
    op.create_index("ix_write_back_points_created_at", "write_back_points", ["created_at"])

    op.create_table(
        "business_quality_gates",
        sa.Column("id", sa.String(length=120), primary_key=True),
        sa.Column("tenant_id", sa.String(length=80), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("case_id", sa.String(length=80), sa.ForeignKey("cases.id"), nullable=True),
        sa.Column("gate_code", sa.String(length=120), nullable=False),
        sa.Column("business_domain", sa.String(length=120), nullable=False),
        sa.Column("object_type", sa.String(length=80), nullable=True),
        sa.Column("object_id", sa.String(length=120), nullable=True),
        sa.Column("gate_type", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=60), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("criteria", json_type, nullable=False, server_default=list_default),
        sa.Column("blocking_policy", json_type, nullable=False, server_default=json_default),
        sa.Column("evidence_refs", json_type, nullable=False, server_default=list_default),
        sa.Column("review_gate_record_id", sa.String(length=120), sa.ForeignKey("review_gate_records.id"), nullable=True),
        sa.Column("metrics_snapshot_id", sa.String(length=120), sa.ForeignKey("metrics_snapshots.id"), nullable=True),
        sa.Column("payload", json_type, nullable=False, server_default=json_default),
        *_timestamps(),
    )
    op.create_index("ix_business_quality_gates_tenant_id", "business_quality_gates", ["tenant_id"])
    op.create_index("ix_business_quality_gates_case_id", "business_quality_gates", ["case_id"])
    op.create_index("ix_business_quality_gates_gate_code", "business_quality_gates", ["gate_code"])
    op.create_index("ix_business_quality_gates_status", "business_quality_gates", ["status"])
    op.create_index("ix_business_quality_gates_review_gate_record_id", "business_quality_gates", ["review_gate_record_id"])
    op.create_index("ix_business_quality_gates_object_ref", "business_quality_gates", ["object_type", "object_id"])
    op.create_index("ix_business_quality_gates_created_at", "business_quality_gates", ["created_at"])

    op.create_table(
        "file_objects",
        sa.Column("id", sa.String(length=120), primary_key=True),
        sa.Column("tenant_id", sa.String(length=80), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("case_id", sa.String(length=80), sa.ForeignKey("cases.id"), nullable=True),
        sa.Column("owner_user_id", sa.String(length=100), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("task_id", sa.String(length=100), sa.ForeignKey("tasks.id"), nullable=True),
        sa.Column("review_id", sa.String(length=120), sa.ForeignKey("reviews.id"), nullable=True),
        sa.Column("media_asset_id", sa.String(length=120), sa.ForeignKey("media_assets.id"), nullable=True),
        sa.Column("object_type", sa.String(length=80), nullable=True),
        sa.Column("object_id", sa.String(length=120), nullable=True),
        sa.Column("storage_key", sa.String(length=500), nullable=False),
        sa.Column("file_name", sa.String(length=240), nullable=False),
        sa.Column("mime_type", sa.String(length=120), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("checksum", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=60), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("access_policy", json_type, nullable=False, server_default=json_default),
        sa.Column("source_refs", json_type, nullable=False, server_default=list_default),
        sa.Column("review_gate_record_id", sa.String(length=120), sa.ForeignKey("review_gate_records.id"), nullable=True),
        sa.Column("payload", json_type, nullable=False, server_default=json_default),
        *_timestamps(),
    )
    op.create_index("ix_file_objects_tenant_id", "file_objects", ["tenant_id"])
    op.create_index("ix_file_objects_case_id", "file_objects", ["case_id"])
    op.create_index("ix_file_objects_owner_user_id", "file_objects", ["owner_user_id"])
    op.create_index("ix_file_objects_task_id", "file_objects", ["task_id"])
    op.create_index("ix_file_objects_review_id", "file_objects", ["review_id"])
    op.create_index("ix_file_objects_media_asset_id", "file_objects", ["media_asset_id"])
    op.create_index("ix_file_objects_status", "file_objects", ["status"])
    op.create_index("ix_file_objects_review_gate_record_id", "file_objects", ["review_gate_record_id"])
    op.create_index("ix_file_objects_object_ref", "file_objects", ["object_type", "object_id"])
    op.create_index("ix_file_objects_created_at", "file_objects", ["created_at"])

    op.create_table(
        "notifications",
        sa.Column("id", sa.String(length=120), primary_key=True),
        sa.Column("tenant_id", sa.String(length=80), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("case_id", sa.String(length=80), sa.ForeignKey("cases.id"), nullable=True),
        sa.Column("recipient_user_id", sa.String(length=100), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("task_id", sa.String(length=100), sa.ForeignKey("tasks.id"), nullable=True),
        sa.Column("review_id", sa.String(length=120), sa.ForeignKey("reviews.id"), nullable=True),
        sa.Column("source_object_type", sa.String(length=80), nullable=True),
        sa.Column("source_object_id", sa.String(length=120), nullable=True),
        sa.Column("notification_type", sa.String(length=80), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("severity", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=60), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payload", json_type, nullable=False, server_default=json_default),
        *_timestamps(),
    )
    op.create_index("ix_notifications_tenant_id", "notifications", ["tenant_id"])
    op.create_index("ix_notifications_case_id", "notifications", ["case_id"])
    op.create_index("ix_notifications_recipient_user_id", "notifications", ["recipient_user_id"])
    op.create_index("ix_notifications_task_id", "notifications", ["task_id"])
    op.create_index("ix_notifications_review_id", "notifications", ["review_id"])
    op.create_index("ix_notifications_status", "notifications", ["status"])
    op.create_index("ix_notifications_source_object_ref", "notifications", ["source_object_type", "source_object_id"])
    op.create_index("ix_notifications_created_at", "notifications", ["created_at"])

    op.create_table(
        "algorithm_runs",
        sa.Column("id", sa.String(length=120), primary_key=True),
        sa.Column("tenant_id", sa.String(length=80), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("case_id", sa.String(length=80), sa.ForeignKey("cases.id"), nullable=True),
        sa.Column("workflow_run_id", sa.String(length=100), sa.ForeignKey("workflow_runs.id"), nullable=True),
        sa.Column("config_version_id", sa.String(length=120), sa.ForeignKey("config_versions.id"), nullable=True),
        sa.Column("write_back_point_id", sa.String(length=120), sa.ForeignKey("write_back_points.id"), nullable=True),
        sa.Column("object_type", sa.String(length=80), nullable=True),
        sa.Column("object_id", sa.String(length=120), nullable=True),
        sa.Column("algorithm_name", sa.String(length=120), nullable=False),
        sa.Column("algorithm_version", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=60), nullable=False),
        sa.Column("input_refs", json_type, nullable=False, server_default=list_default),
        sa.Column("output_refs", json_type, nullable=False, server_default=list_default),
        sa.Column("output", json_type, nullable=False, server_default=json_default),
        sa.Column("metrics", json_type, nullable=False, server_default=json_default),
        sa.Column("error_code", sa.String(length=120), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("trace_id", sa.String(length=120), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payload", json_type, nullable=False, server_default=json_default),
        *_timestamps(),
    )
    op.create_index("ix_algorithm_runs_tenant_id", "algorithm_runs", ["tenant_id"])
    op.create_index("ix_algorithm_runs_case_id", "algorithm_runs", ["case_id"])
    op.create_index("ix_algorithm_runs_workflow_run_id", "algorithm_runs", ["workflow_run_id"])
    op.create_index("ix_algorithm_runs_config_version_id", "algorithm_runs", ["config_version_id"])
    op.create_index("ix_algorithm_runs_algorithm_name", "algorithm_runs", ["algorithm_name"])
    op.create_index("ix_algorithm_runs_status", "algorithm_runs", ["status"])
    op.create_index("ix_algorithm_runs_object_ref", "algorithm_runs", ["object_type", "object_id"])
    op.create_index("ix_algorithm_runs_created_at", "algorithm_runs", ["created_at"])


def downgrade() -> None:
    raise RuntimeError("Downgrade is intentionally disabled for S1 contract/review traceability schema.")
