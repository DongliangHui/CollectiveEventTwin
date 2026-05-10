from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, JSON, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Case(Base, TimestampMixin):
    __tablename__ = "cases"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    slug: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    scenario_type: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="active", nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class Tenant(Base, TimestampMixin):
    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="active", nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(80), ForeignKey("tenants.id"), index=True, nullable=False)
    username: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(260), nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="active", nullable=False)
    failed_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class Role(Base, TimestampMixin):
    __tablename__ = "roles"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(80), ForeignKey("tenants.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(String(240), nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="active", nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class Permission(Base, TimestampMixin):
    __tablename__ = "permissions"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    code: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(String(240), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class UserRole(Base):
    __tablename__ = "user_roles"

    user_id: Mapped[str] = mapped_column(String(100), ForeignKey("users.id"), primary_key=True)
    role_id: Mapped[str] = mapped_column(String(100), ForeignKey("roles.id"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RolePermission(Base):
    __tablename__ = "role_permissions"

    role_id: Mapped[str] = mapped_column(String(100), ForeignKey("roles.id"), primary_key=True)
    permission_id: Mapped[str] = mapped_column(String(120), ForeignKey("permissions.id"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuthSession(Base, TimestampMixin):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(80), ForeignKey("tenants.id"), index=True, nullable=False)
    user_id: Mapped[str] = mapped_column(String(100), ForeignKey("users.id"), index=True, nullable=False)
    access_token_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    refresh_token_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="active", nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class ReviewTemplate(Base, TimestampMixin):
    __tablename__ = "review_templates"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    object_type: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="active", nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class Review(Base, TimestampMixin):
    __tablename__ = "reviews"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(80), ForeignKey("tenants.id"), index=True, nullable=False)
    template_id: Mapped[str] = mapped_column(String(100), ForeignKey("review_templates.id"), index=True, nullable=False)
    object_type: Mapped[str] = mapped_column(String(80), nullable=False)
    object_id: Mapped[str] = mapped_column(String(200), nullable=False)
    object_version: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    reviewer_id: Mapped[str | None] = mapped_column(String(100), ForeignKey("users.id"), nullable=True)
    blocker_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    waived_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    waiver_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class ReviewResult(Base):
    __tablename__ = "review_results"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    review_id: Mapped[str] = mapped_column(String(120), ForeignKey("reviews.id"), index=True, nullable=False)
    reviewer_id: Mapped[str | None] = mapped_column(String(100), ForeignKey("users.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    findings: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    blockers: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class WorkflowRunEvent(Base):
    __tablename__ = "workflow_run_events"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    workflow_run_id: Mapped[str] = mapped_column(String(100), ForeignKey("workflow_runs.id"), index=True, nullable=False)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OpsErrorQueue(Base, TimestampMixin):
    __tablename__ = "ops_error_queue"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    source: Mapped[str] = mapped_column(String(120), nullable=False)
    severity: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class OpsRetryQueue(Base, TimestampMixin):
    __tablename__ = "ops_retry_queue"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    target_type: Mapped[str] = mapped_column(String(80), nullable=False)
    target_id: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class MetricsSnapshot(Base):
    __tablename__ = "metrics_snapshots"
    __table_args__ = (Index("ix_metrics_snapshots_tenant_scope", "tenant_id", "metric_scope", "captured_at"),)

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    tenant_id: Mapped[str | None] = mapped_column(String(80), ForeignKey("tenants.id"), nullable=True)
    metric_scope: Mapped[str] = mapped_column(String(120), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DataSource(Base, TimestampMixin):
    __tablename__ = "data_sources"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(80), ForeignKey("tenants.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    source_type: Mapped[str] = mapped_column(String(60), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    policy: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class DataSourceVersion(Base, TimestampMixin):
    __tablename__ = "data_source_versions"
    __table_args__ = (
        Index("ix_data_source_versions_tenant_id", "tenant_id"),
        Index("ix_data_source_versions_data_source_id", "data_source_id"),
        Index("ix_data_source_versions_status", "status"),
    )

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(80), ForeignKey("tenants.id"), nullable=False)
    data_source_id: Mapped[str] = mapped_column(String(120), ForeignKey("data_sources.id"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    config_hash: Mapped[str] = mapped_column(String(120), nullable=False)
    policy_snapshot: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    published_by_id: Mapped[str | None] = mapped_column(String(100), ForeignKey("users.id"), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SourcePolicy(Base, TimestampMixin):
    __tablename__ = "source_policies"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    data_source_id: Mapped[str] = mapped_column(String(120), ForeignKey("data_sources.id"), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(240), nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class SourceHealth(Base, TimestampMixin):
    __tablename__ = "source_health"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    data_source_id: Mapped[str] = mapped_column(String(120), ForeignKey("data_sources.id"), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    last_run_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    success_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failure_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error_code: Mapped[str | None] = mapped_column(String(120), nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class CollectionJob(Base, TimestampMixin):
    __tablename__ = "collection_jobs"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(80), ForeignKey("tenants.id"), index=True, nullable=False)
    data_source_id: Mapped[str] = mapped_column(String(120), ForeignKey("data_sources.id"), index=True, nullable=False)
    created_by_id: Mapped[str | None] = mapped_column(String(100), ForeignKey("users.id"), index=True, nullable=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    schedule: Mapped[str | None] = mapped_column(String(120), nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class CollectionRun(Base, TimestampMixin):
    __tablename__ = "collection_runs"
    __table_args__ = (
        Index("ix_collection_runs_job_created_id", "collection_job_id", "created_at", "id"),
        Index("ix_collection_runs_source_created_id", "data_source_id", "created_at", "id"),
    )

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    collection_job_id: Mapped[str] = mapped_column(String(120), ForeignKey("collection_jobs.id"), index=True, nullable=False)
    data_source_id: Mapped[str] = mapped_column(String(120), ForeignKey("data_sources.id"), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    record_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(120), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    trace_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class CollectionRunEvent(Base):
    __tablename__ = "collection_run_events"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    collection_run_id: Mapped[str] = mapped_column(String(120), ForeignKey("collection_runs.id"), index=True, nullable=False)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RawRecord(Base, TimestampMixin):
    __tablename__ = "raw_records"
    __table_args__ = (
        Index("ix_raw_records_tenant_created_id", "tenant_id", "created_at", "id"),
        Index("ix_raw_records_tenant_source_created", "tenant_id", "data_source_id", "created_at", "id"),
        Index("ix_raw_records_tenant_collection_run", "tenant_id", "collection_run_id"),
        Index("ix_raw_records_tenant_source_type_created", "tenant_id", "source_type", "created_at", "id"),
        Index("ix_raw_records_tenant_status_created", "tenant_id", "status", "created_at", "id"),
        Index("ux_raw_records_source_type_dedupe_key", "data_source_id", "source_type", "dedupe_key", unique=True),
        Index("ux_raw_records_rss_guid_key", "data_source_id", "source_type", "rss_guid_key", unique=True),
        Index("ux_raw_records_rss_link_key", "data_source_id", "source_type", "rss_link_key", unique=True),
        Index("ux_raw_records_webhook_delivery_key", "data_source_id", "source_type", "webhook_delivery_key", unique=True),
    )

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(80), ForeignKey("tenants.id"), index=True, nullable=False)
    data_source_id: Mapped[str] = mapped_column(String(120), ForeignKey("data_sources.id"), index=True, nullable=False)
    collection_run_id: Mapped[str] = mapped_column(String(120), ForeignKey("collection_runs.id"), index=True, nullable=False)
    source_type: Mapped[str] = mapped_column(String(60), nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(120), nullable=False)
    dedupe_key: Mapped[str | None] = mapped_column(String(240), nullable=True, index=True)
    rss_guid_key: Mapped[str | None] = mapped_column(String(240), nullable=True, index=True)
    rss_link_key: Mapped[str | None] = mapped_column(String(240), nullable=True, index=True)
    webhook_delivery_key: Mapped[str | None] = mapped_column(String(240), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    city_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class RawRecordPayload(Base):
    __tablename__ = "raw_record_payloads"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    raw_record_id: Mapped[str] = mapped_column(String(120), ForeignKey("raw_records.id"), index=True, nullable=False)
    content_text: Mapped[str] = mapped_column(Text, nullable=False)
    masked_text: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RawRecordLabel(Base):
    __tablename__ = "raw_record_labels"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    raw_record_id: Mapped[str] = mapped_column(String(120), ForeignKey("raw_records.id"), index=True, nullable=False)
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    actor_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    reason: Mapped[str | None] = mapped_column(String(240), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MediaAsset(Base, TimestampMixin):
    __tablename__ = "media_assets"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    raw_record_id: Mapped[str] = mapped_column(String(120), ForeignKey("raw_records.id"), index=True, nullable=False)
    media_type: Mapped[str] = mapped_column(String(40), nullable=False)
    uri: Mapped[str] = mapped_column(String(400), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class MediaProcessingRun(Base, TimestampMixin):
    __tablename__ = "media_processing_runs"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    media_asset_id: Mapped[str] = mapped_column(String(120), ForeignKey("media_assets.id"), index=True, nullable=False)
    processor: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    output: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    trace_id: Mapped[str | None] = mapped_column(String(120), nullable=True)


class LineageEdge(Base):
    __tablename__ = "lineage_edges"
    __table_args__ = (
        Index("ix_lineage_edges_to_object", "to_object_type", "to_object_id"),
        Index("ix_lineage_edges_from_object", "from_object_type", "from_object_id"),
    )

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    from_object_type: Mapped[str] = mapped_column(String(80), nullable=False)
    from_object_id: Mapped[str] = mapped_column(String(120), nullable=False)
    to_object_type: Mapped[str] = mapped_column(String(80), nullable=False)
    to_object_id: Mapped[str] = mapped_column(String(120), nullable=False)
    relation: Mapped[str] = mapped_column(String(80), nullable=False)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ImportRun(Base, TimestampMixin):
    __tablename__ = "import_runs"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(80), ForeignKey("tenants.id"), index=True, nullable=False)
    data_source_id: Mapped[str] = mapped_column(String(120), ForeignKey("data_sources.id"), index=True, nullable=False)
    collection_run_id: Mapped[str | None] = mapped_column(String(120), ForeignKey("collection_runs.id"), index=True, nullable=True)
    import_type: Mapped[str] = mapped_column(String(60), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    record_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(120), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    trace_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class NormalizationRun(Base, TimestampMixin):
    __tablename__ = "normalization_runs"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(80), ForeignKey("tenants.id"), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    input_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    output_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rule_version: Mapped[str] = mapped_column(String(80), nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(120), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    trace_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class RawRecordNormalization(Base):
    __tablename__ = "raw_record_normalizations"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    normalization_run_id: Mapped[str] = mapped_column(String(120), ForeignKey("normalization_runs.id"), index=True, nullable=False)
    raw_record_id: Mapped[str] = mapped_column(String(120), ForeignKey("raw_records.id"), index=True, nullable=False)
    normalized_title: Mapped[str] = mapped_column(String(240), nullable=False)
    normalized_text: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(String(40), nullable=False)
    region_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DeduplicationRun(Base, TimestampMixin):
    __tablename__ = "deduplication_runs"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(80), ForeignKey("tenants.id"), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    input_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duplicate_group_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rule_version: Mapped[str] = mapped_column(String(80), nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(120), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    trace_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class RawRecordDedupGroup(Base):
    __tablename__ = "raw_record_dedup_groups"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    deduplication_run_id: Mapped[str] = mapped_column(String(120), ForeignKey("deduplication_runs.id"), index=True, nullable=False)
    group_key: Mapped[str] = mapped_column(String(160), nullable=False)
    kept_raw_record_id: Mapped[str] = mapped_column(String(120), ForeignKey("raw_records.id"), nullable=False)
    duplicate_raw_record_ids: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DataQualityRun(Base, TimestampMixin):
    __tablename__ = "data_quality_runs"
    __table_args__ = (Index("ix_data_quality_runs_tenant_created_id", "tenant_id", "created_at", "id"),)

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(80), ForeignKey("tenants.id"), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    input_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    issue_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rule_version: Mapped[str] = mapped_column(String(80), nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(120), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    trace_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class RawRecordQualityIssue(Base):
    __tablename__ = "raw_record_quality_issues"
    __table_args__ = (
        Index("ix_raw_record_quality_issues_tenant_created", "tenant_id", "created_at", "id"),
        Index("ix_raw_record_quality_issues_tenant_type_created", "tenant_id", "issue_type", "created_at", "id"),
        Index("ix_raw_record_quality_issues_tenant_severity_created", "tenant_id", "severity", "created_at", "id"),
        Index("ix_raw_record_quality_issues_tenant_run_created", "tenant_id", "data_quality_run_id", "created_at", "id"),
        Index("ix_raw_record_quality_issues_tenant_raw_created", "tenant_id", "raw_record_id", "created_at", "id"),
        Index("ix_raw_record_quality_issues_created_id", "created_at", "id"),
        Index("ix_raw_record_quality_issues_type_created", "issue_type", "created_at", "id"),
        Index("ix_raw_record_quality_issues_severity_created", "severity", "created_at", "id"),
    )

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(80), ForeignKey("tenants.id"), index=True, nullable=False)
    data_quality_run_id: Mapped[str] = mapped_column(String(120), ForeignKey("data_quality_runs.id"), index=True, nullable=False)
    raw_record_id: Mapped[str] = mapped_column(String(120), ForeignKey("raw_records.id"), index=True, nullable=False)
    issue_type: Mapped[str] = mapped_column(String(80), nullable=False)
    severity: Mapped[str] = mapped_column(String(40), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class City(Base, TimestampMixin):
    __tablename__ = "cities"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(80), ForeignKey("tenants.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    region_code: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="active", nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class Topic(Base, TimestampMixin):
    __tablename__ = "topics"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(80), ForeignKey("tenants.id"), index=True, nullable=False)
    city_id: Mapped[str] = mapped_column(String(80), ForeignKey("cities.id"), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    heat_score: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    created_from_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_from_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class CityEvent(Base, TimestampMixin):
    __tablename__ = "city_events"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(80), ForeignKey("tenants.id"), index=True, nullable=False)
    city_id: Mapped[str] = mapped_column(String(80), ForeignKey("cities.id"), index=True, nullable=False)
    topic_id: Mapped[str | None] = mapped_column(String(120), ForeignKey("topics.id"), index=True, nullable=True)
    raw_record_id: Mapped[str | None] = mapped_column(String(120), ForeignKey("raw_records.id"), index=True, nullable=True)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    heat_score: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    risk_score: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    evidence_refs: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class CityMapState(Base, TimestampMixin):
    __tablename__ = "city_map_states"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(80), ForeignKey("tenants.id"), index=True, nullable=False)
    city_id: Mapped[str] = mapped_column(String(80), ForeignKey("cities.id"), index=True, nullable=False)
    user_id: Mapped[str] = mapped_column(String(100), ForeignKey("users.id"), index=True, nullable=False)
    layer_mode: Mapped[str] = mapped_column(String(40), nullable=False)
    filters: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class SignalPackage(Base, TimestampMixin):
    __tablename__ = "signal_packages"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(80), ForeignKey("tenants.id"), index=True, nullable=False)
    topic_id: Mapped[str] = mapped_column(String(120), ForeignKey("topics.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    rule_version: Mapped[str] = mapped_column(String(80), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class SignalPackageItem(Base):
    __tablename__ = "signal_package_items"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    signal_package_id: Mapped[str] = mapped_column(String(120), ForeignKey("signal_packages.id"), index=True, nullable=False)
    signal_id: Mapped[str] = mapped_column(String(100), ForeignKey("signals.id"), index=True, nullable=False)
    rank: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SourceRecord(Base, TimestampMixin):
    __tablename__ = "source_records"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    case_id: Mapped[str] = mapped_column(String(80), ForeignKey("cases.id"), index=True, nullable=False)
    source_id: Mapped[str] = mapped_column(String(100), nullable=False)
    source_name: Mapped[str] = mapped_column(String(200), nullable=False)
    access_mode: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    trust: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    accepted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    blocked_reason: Mapped[str | None] = mapped_column(String(160), nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class Signal(Base, TimestampMixin):
    __tablename__ = "signals"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    case_id: Mapped[str] = mapped_column(String(80), ForeignKey("cases.id"), index=True, nullable=False)
    topic_id: Mapped[str | None] = mapped_column(String(120), ForeignKey("topics.id"), index=True, nullable=True)
    mainline_id: Mapped[str | None] = mapped_column(String(100), index=True, nullable=True)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[str] = mapped_column(String(20), nullable=False)
    region_id: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(60), nullable=False)
    scores: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class Evidence(Base, TimestampMixin):
    __tablename__ = "evidence"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    case_id: Mapped[str] = mapped_column(String(80), ForeignKey("cases.id"), index=True, nullable=False)
    signal_id: Mapped[str | None] = mapped_column(String(100), ForeignKey("signals.id"), index=True, nullable=True)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    excerpt: Mapped[str] = mapped_column(Text, nullable=False)
    masked_excerpt: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(200), nullable=False)
    credibility: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(60), nullable=False)
    sensitivity: Mapped[str] = mapped_column(String(80), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class EvidenceReview(Base, TimestampMixin):
    __tablename__ = "evidence_reviews"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(80), ForeignKey("tenants.id"), index=True, nullable=False)
    case_id: Mapped[str] = mapped_column(String(80), ForeignKey("cases.id"), index=True, nullable=False)
    topic_id: Mapped[str | None] = mapped_column(String(120), ForeignKey("topics.id"), index=True, nullable=True)
    evidence_id: Mapped[str] = mapped_column(String(100), ForeignKey("evidence.id"), index=True, nullable=False)
    signal_id: Mapped[str | None] = mapped_column(String(100), ForeignKey("signals.id"), index=True, nullable=True)
    status: Mapped[str] = mapped_column(String(60), nullable=False)
    reviewer_id: Mapped[str | None] = mapped_column(String(100), ForeignKey("users.id"), nullable=True)
    decision: Mapped[str | None] = mapped_column(String(80), nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class EvidenceMediaLink(Base, TimestampMixin):
    __tablename__ = "evidence_media_links"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(80), ForeignKey("tenants.id"), index=True, nullable=False)
    evidence_id: Mapped[str] = mapped_column(String(100), ForeignKey("evidence.id"), index=True, nullable=False)
    media_asset_id: Mapped[str] = mapped_column(String(120), ForeignKey("media_assets.id"), index=True, nullable=False)
    relation: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(60), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class RiskFactor(Base, TimestampMixin):
    __tablename__ = "risk_factors"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    case_id: Mapped[str] = mapped_column(String(80), ForeignKey("cases.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    category: Mapped[str] = mapped_column(String(80), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(60), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class Mainline(Base, TimestampMixin):
    __tablename__ = "mainlines"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    case_id: Mapped[str] = mapped_column(String(80), ForeignKey("cases.id"), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(60), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class MainlineVersion(Base, TimestampMixin):
    __tablename__ = "mainline_versions"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(80), ForeignKey("tenants.id"), index=True, nullable=False)
    mainline_id: Mapped[str] = mapped_column(String(100), ForeignKey("mainlines.id"), index=True, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(60), nullable=False)
    diff: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class MainlineNode(Base, TimestampMixin):
    __tablename__ = "mainline_nodes"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(80), ForeignKey("tenants.id"), index=True, nullable=False)
    mainline_id: Mapped[str] = mapped_column(String(100), ForeignKey("mainlines.id"), index=True, nullable=False)
    node_type: Mapped[str] = mapped_column(String(80), nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(60), nullable=False)
    evidence_refs: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class WorldState(Base, TimestampMixin):
    __tablename__ = "world_states"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    case_id: Mapped[str] = mapped_column(String(80), ForeignKey("cases.id"), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    status: Mapped[str] = mapped_column(String(60), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class CaseGraphNode(Base, TimestampMixin):
    __tablename__ = "case_graph_nodes"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(80), ForeignKey("tenants.id"), index=True, nullable=False)
    case_id: Mapped[str] = mapped_column(String(80), ForeignKey("cases.id"), index=True, nullable=False)
    topic_id: Mapped[str | None] = mapped_column(String(120), ForeignKey("topics.id"), index=True, nullable=True)
    mainline_id: Mapped[str] = mapped_column(String(100), ForeignKey("mainlines.id"), index=True, nullable=False)
    world_state_id: Mapped[str | None] = mapped_column(String(100), ForeignKey("world_states.id"), index=True, nullable=True)
    node_type: Mapped[str] = mapped_column(String(80), nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    status: Mapped[str] = mapped_column(String(60), nullable=False)
    evidence_refs: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class Stakeholder(Base, TimestampMixin):
    __tablename__ = "stakeholders"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(80), ForeignKey("tenants.id"), index=True, nullable=False)
    case_id: Mapped[str] = mapped_column(String(80), ForeignKey("cases.id"), index=True, nullable=False)
    topic_id: Mapped[str | None] = mapped_column(String(120), ForeignKey("topics.id"), index=True, nullable=True)
    mainline_id: Mapped[str] = mapped_column(String(100), ForeignKey("mainlines.id"), index=True, nullable=False)
    graph_node_id: Mapped[str | None] = mapped_column(String(120), ForeignKey("case_graph_nodes.id"), index=True, nullable=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    role: Mapped[str] = mapped_column(String(120), nullable=False)
    stance: Mapped[str] = mapped_column(String(240), nullable=False)
    status: Mapped[str] = mapped_column(String(60), nullable=False)
    reviewer_id: Mapped[str | None] = mapped_column(String(100), ForeignKey("users.id"), nullable=True)
    evidence_refs: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class WorldlineNode(Base, TimestampMixin):
    __tablename__ = "worldline_nodes"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    case_id: Mapped[str] = mapped_column(String(80), ForeignKey("cases.id"), index=True, nullable=False)
    tenant_id: Mapped[str | None] = mapped_column(String(80), ForeignKey("tenants.id"), index=True, nullable=True)
    worldline_run_id: Mapped[str | None] = mapped_column(String(120), ForeignKey("worldline_runs.id"), index=True, nullable=True)
    world_state_id: Mapped[str | None] = mapped_column(String(100), ForeignKey("world_states.id"), index=True, nullable=True)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    branch: Mapped[str] = mapped_column(String(40), nullable=False)
    probability: Mapped[int] = mapped_column(Integer, nullable=False)
    risk: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(60), nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    evidence_refs: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class WorldlineRun(Base, TimestampMixin):
    __tablename__ = "worldline_runs"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(80), ForeignKey("tenants.id"), index=True, nullable=False)
    case_id: Mapped[str] = mapped_column(String(80), ForeignKey("cases.id"), index=True, nullable=False)
    world_state_id: Mapped[str] = mapped_column(String(100), ForeignKey("world_states.id"), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(60), nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    current_step: Mapped[str | None] = mapped_column(String(120), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(120), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_retryable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class WorldlineEdge(Base, TimestampMixin):
    __tablename__ = "worldline_edges"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(80), ForeignKey("tenants.id"), index=True, nullable=False)
    worldline_run_id: Mapped[str] = mapped_column(String(120), ForeignKey("worldline_runs.id"), index=True, nullable=False)
    from_node_id: Mapped[str] = mapped_column(String(100), ForeignKey("worldline_nodes.id"), nullable=False)
    to_node_id: Mapped[str] = mapped_column(String(100), ForeignKey("worldline_nodes.id"), nullable=False)
    probability_delta: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class WorldlineIntervention(Base, TimestampMixin):
    __tablename__ = "worldline_interventions"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(80), ForeignKey("tenants.id"), index=True, nullable=False)
    worldline_run_id: Mapped[str] = mapped_column(String(120), ForeignKey("worldline_runs.id"), index=True, nullable=False)
    action: Mapped[str] = mapped_column(String(160), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    constraints: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class CouncilSession(Base, TimestampMixin):
    __tablename__ = "council_sessions"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    case_id: Mapped[str] = mapped_column(String(80), ForeignKey("cases.id"), index=True, nullable=False)
    node_id: Mapped[str] = mapped_column(String(100), nullable=False)
    hypothesis: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(60), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class LlmProvider(Base, TimestampMixin):
    __tablename__ = "llm_providers"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(80), ForeignKey("tenants.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(String(60), nullable=False)
    model_defaults: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class PromptTemplate(Base, TimestampMixin):
    __tablename__ = "prompt_templates"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(80), ForeignKey("tenants.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    version: Mapped[str] = mapped_column(String(80), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(80), nullable=False)
    template: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class LlmCall(Base, TimestampMixin):
    __tablename__ = "llm_calls"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(80), ForeignKey("tenants.id"), index=True, nullable=False)
    provider_id: Mapped[str] = mapped_column(String(120), ForeignKey("llm_providers.id"), index=True, nullable=False)
    prompt_template_id: Mapped[str | None] = mapped_column(String(120), ForeignKey("prompt_templates.id"), index=True, nullable=True)
    object_type: Mapped[str] = mapped_column(String(80), nullable=False)
    object_id: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(60), nullable=False)
    tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cost: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    input_refs: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    output: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class AgentTemplate(Base, TimestampMixin):
    __tablename__ = "agent_templates"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(80), ForeignKey("tenants.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    version: Mapped[str] = mapped_column(String(80), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class AgentProfile(Base, TimestampMixin):
    __tablename__ = "agent_profiles"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(80), ForeignKey("tenants.id"), index=True, nullable=False)
    stakeholder_id: Mapped[str] = mapped_column(String(120), ForeignKey("stakeholders.id"), index=True, nullable=False)
    worldline_run_id: Mapped[str] = mapped_column(String(120), ForeignKey("worldline_runs.id"), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(60), nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    files: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    evidence_refs: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class AgentProfileFile(Base, TimestampMixin):
    __tablename__ = "agent_profile_files"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(80), ForeignKey("tenants.id"), index=True, nullable=False)
    agent_profile_id: Mapped[str] = mapped_column(String(120), ForeignKey("agent_profiles.id"), index=True, nullable=False)
    file_type: Mapped[str] = mapped_column(String(40), nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class CouncilMessage(Base, TimestampMixin):
    __tablename__ = "council_messages"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(80), ForeignKey("tenants.id"), index=True, nullable=False)
    council_session_id: Mapped[str] = mapped_column(String(100), ForeignKey("council_sessions.id"), index=True, nullable=False)
    agent_profile_id: Mapped[str | None] = mapped_column(String(120), ForeignKey("agent_profiles.id"), nullable=True)
    role: Mapped[str] = mapped_column(String(120), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_refs: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class CouncilResult(Base, TimestampMixin):
    __tablename__ = "council_results"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(80), ForeignKey("tenants.id"), index=True, nullable=False)
    council_session_id: Mapped[str] = mapped_column(String(100), ForeignKey("council_sessions.id"), index=True, nullable=False)
    worldline_run_id: Mapped[str] = mapped_column(String(120), ForeignKey("worldline_runs.id"), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(60), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_refs: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class BlockedClaim(Base, TimestampMixin):
    __tablename__ = "blocked_claims"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(80), ForeignKey("tenants.id"), index=True, nullable=False)
    claim: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    source_ref: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    llm_call_id: Mapped[str | None] = mapped_column(String(120), ForeignKey("llm_calls.id"), index=True, nullable=True)
    council_result_id: Mapped[str | None] = mapped_column(String(120), ForeignKey("council_results.id"), index=True, nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class Report(Base, TimestampMixin):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    tenant_id: Mapped[str | None] = mapped_column(String(80), ForeignKey("tenants.id"), index=True, nullable=True)
    case_id: Mapped[str] = mapped_column(String(80), ForeignKey("cases.id"), index=True, nullable=False)
    topic_id: Mapped[str | None] = mapped_column(String(120), ForeignKey("topics.id"), index=True, nullable=True)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    human_confirmed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(60), nullable=False)
    current_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    review_id: Mapped[str | None] = mapped_column(String(120), ForeignKey("reviews.id"), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    exported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class ReportVersion(Base, TimestampMixin):
    __tablename__ = "report_versions"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(80), ForeignKey("tenants.id"), index=True, nullable=False)
    report_id: Mapped[str] = mapped_column(String(100), ForeignKey("reports.id"), index=True, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(60), nullable=False)
    sections: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    diff: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class ReportClaim(Base, TimestampMixin):
    __tablename__ = "report_claims"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(80), ForeignKey("tenants.id"), index=True, nullable=False)
    report_id: Mapped[str] = mapped_column(String(100), ForeignKey("reports.id"), index=True, nullable=False)
    report_version_id: Mapped[str | None] = mapped_column(String(120), ForeignKey("report_versions.id"), index=True, nullable=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    claim_type: Mapped[str] = mapped_column(String(80), nullable=False)
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(60), nullable=False)
    validation_status: Mapped[str] = mapped_column(String(60), nullable=False)
    source_object_type: Mapped[str] = mapped_column(String(80), nullable=False)
    source_object_id: Mapped[str] = mapped_column(String(120), nullable=False)
    evidence_refs: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class ReportExport(Base, TimestampMixin):
    __tablename__ = "report_exports"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(80), ForeignKey("tenants.id"), index=True, nullable=False)
    report_id: Mapped[str] = mapped_column(String(100), ForeignKey("reports.id"), index=True, nullable=False)
    format: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(60), nullable=False)
    file_uri: Mapped[str | None] = mapped_column(String(500), nullable=True)
    watermark: Mapped[str] = mapped_column(String(120), nullable=False)
    content_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class Task(Base, TimestampMixin):
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    tenant_id: Mapped[str | None] = mapped_column(String(80), ForeignKey("tenants.id"), index=True, nullable=True)
    case_id: Mapped[str] = mapped_column(String(80), ForeignKey("cases.id"), index=True, nullable=False)
    report_id: Mapped[str | None] = mapped_column(String(100), ForeignKey("reports.id"), index=True, nullable=True)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    owner: Mapped[str] = mapped_column(String(120), nullable=False)
    due_label: Mapped[str] = mapped_column(String(80), nullable=False)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(60), nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    evidence_refs: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class TaskEvent(Base):
    __tablename__ = "task_events"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    tenant_id: Mapped[str | None] = mapped_column(String(80), ForeignKey("tenants.id"), index=True, nullable=True)
    task_id: Mapped[str] = mapped_column(String(100), ForeignKey("tasks.id"), index=True, nullable=False)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(60), nullable=True)
    to_status: Mapped[str | None] = mapped_column(String(60), nullable=True)
    actor_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Retrospective(Base, TimestampMixin):
    __tablename__ = "retrospectives"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(80), ForeignKey("tenants.id"), index=True, nullable=False)
    report_id: Mapped[str] = mapped_column(String(100), ForeignKey("reports.id"), index=True, nullable=False)
    case_id: Mapped[str] = mapped_column(String(80), ForeignKey("cases.id"), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(60), nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    review_id: Mapped[str | None] = mapped_column(String(120), ForeignKey("reviews.id"), nullable=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    source_refs: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class KnowledgeItem(Base, TimestampMixin):
    __tablename__ = "knowledge_items"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(80), ForeignKey("tenants.id"), index=True, nullable=False)
    retrospective_id: Mapped[str] = mapped_column(String(120), ForeignKey("retrospectives.id"), index=True, nullable=False)
    report_id: Mapped[str] = mapped_column(String(100), ForeignKey("reports.id"), index=True, nullable=False)
    case_id: Mapped[str] = mapped_column(String(80), ForeignKey("cases.id"), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(60), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source_refs: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class CaseLibraryEntry(Base, TimestampMixin):
    __tablename__ = "case_library_entries"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(80), ForeignKey("tenants.id"), index=True, nullable=False)
    case_id: Mapped[str] = mapped_column(String(80), ForeignKey("cases.id"), index=True, nullable=False)
    retrospective_id: Mapped[str] = mapped_column(String(120), ForeignKey("retrospectives.id"), index=True, nullable=False)
    knowledge_item_id: Mapped[str] = mapped_column(String(120), ForeignKey("knowledge_items.id"), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    status: Mapped[str] = mapped_column(String(60), nullable=False)
    tags: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    source_refs: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class CaseLibraryApplication(Base, TimestampMixin):
    __tablename__ = "case_library_applications"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(80), ForeignKey("tenants.id"), index=True, nullable=False)
    case_id: Mapped[str] = mapped_column(String(80), ForeignKey("cases.id"), index=True, nullable=False)
    case_library_entry_id: Mapped[str] = mapped_column(String(120), ForeignKey("case_library_entries.id"), index=True, nullable=False)
    target_object_type: Mapped[str] = mapped_column(String(80), nullable=False)
    target_object_id: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(60), nullable=False)
    conflict_summary: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    source_refs: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class ConfigVersion(Base, TimestampMixin):
    __tablename__ = "config_versions"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(80), ForeignKey("tenants.id"), index=True, nullable=False)
    config_type: Mapped[str] = mapped_column(String(80), nullable=False)
    version: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(60), nullable=False)
    review_id: Mapped[str | None] = mapped_column(String(120), ForeignKey("reviews.id"), nullable=True)
    regression_workflow_run_id: Mapped[str | None] = mapped_column(String(100), ForeignKey("workflow_runs.id"), nullable=True)
    parent_version_id: Mapped[str | None] = mapped_column(String(120), ForeignKey("config_versions.id"), nullable=True)
    input_refs: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    impact_scope: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class ConfigRelease(Base, TimestampMixin):
    __tablename__ = "config_releases"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(80), ForeignKey("tenants.id"), index=True, nullable=False)
    config_version_id: Mapped[str] = mapped_column(String(120), ForeignKey("config_versions.id"), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(60), nullable=False)
    impact_scope: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class WorkflowRun(Base, TimestampMixin):
    __tablename__ = "workflow_runs"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    case_id: Mapped[str] = mapped_column(String(80), ForeignKey("cases.id"), index=True, nullable=False)
    tenant_id: Mapped[str | None] = mapped_column(String(80), ForeignKey("tenants.id"), index=True, nullable=True)
    workflow_name: Mapped[str] = mapped_column(String(120), nullable=False)
    workflow_id: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(String(60), nullable=False)
    started_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    trace_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    tenant_id: Mapped[str | None] = mapped_column(String(80), ForeignKey("tenants.id"), index=True, nullable=True)
    case_id: Mapped[str | None] = mapped_column(String(80), ForeignKey("cases.id"), index=True, nullable=True)
    actor_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    actor: Mapped[str] = mapped_column(String(120), nullable=False)
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    object_type: Mapped[str] = mapped_column(String(80), nullable=False)
    object_id: Mapped[str] = mapped_column(String(120), nullable=False)
    object_version: Mapped[str | None] = mapped_column(String(80), nullable=True)
    reason: Mapped[str | None] = mapped_column(String(240), nullable=True)
    before: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    after: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    diff: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    trace_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(80), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(240), nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ReviewChecklistVersion(Base, TimestampMixin):
    __tablename__ = "review_checklist_versions"
    __table_args__ = (Index("ix_review_checklist_versions_created_at", "created_at"),)

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(80), ForeignKey("tenants.id"), index=True, nullable=False)
    artifact_type: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    version: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(60), index=True, nullable=False)
    checklist_schema: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    items: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    published_by_id: Mapped[str | None] = mapped_column(String(100), ForeignKey("users.id"), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class ReviewGateRecord(Base, TimestampMixin):
    __tablename__ = "review_gate_records"
    __table_args__ = (
        Index("ix_review_gate_records_artifact_ref", "artifact_type", "artifact_id"),
        Index("ix_review_gate_records_created_at", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(80), ForeignKey("tenants.id"), index=True, nullable=False)
    case_id: Mapped[str | None] = mapped_column(String(80), ForeignKey("cases.id"), index=True, nullable=True)
    review_id: Mapped[str | None] = mapped_column(String(120), ForeignKey("reviews.id"), index=True, nullable=True)
    task_id: Mapped[str] = mapped_column(String(100), ForeignKey("tasks.id"), index=True, nullable=False)
    checklist_version_id: Mapped[str | None] = mapped_column(
        String(120), ForeignKey("review_checklist_versions.id"), index=True, nullable=True
    )
    artifact_type: Mapped[str] = mapped_column(String(80), nullable=False)
    artifact_id: Mapped[str] = mapped_column(String(200), nullable=False)
    artifact_version: Mapped[str | None] = mapped_column(String(80), nullable=True)
    gate_code: Mapped[str | None] = mapped_column(String(120), nullable=True)
    reviewer_id: Mapped[str] = mapped_column(String(100), ForeignKey("users.id"), index=True, nullable=False)
    implemented_by_id: Mapped[str | None] = mapped_column(String(100), ForeignKey("users.id"), nullable=True)
    result: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(60), index=True, nullable=False)
    findings: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    blockers: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    evidence_refs: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    audit_log_id: Mapped[str | None] = mapped_column(String(120), ForeignKey("audit_logs.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class PageSurfaceContract(Base, TimestampMixin):
    __tablename__ = "page_surface_contracts"
    __table_args__ = (
        Index("ix_page_surface_contracts_object_ref", "object_type", "object_id"),
        Index("ix_page_surface_contracts_created_at", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(80), ForeignKey("tenants.id"), index=True, nullable=False)
    case_id: Mapped[str | None] = mapped_column(String(80), ForeignKey("cases.id"), index=True, nullable=True)
    surface_id: Mapped[str] = mapped_column(String(160), index=True, nullable=False)
    route: Mapped[str] = mapped_column(String(240), nullable=False)
    page_key: Mapped[str] = mapped_column(String(80), nullable=False)
    surface_type: Mapped[str] = mapped_column(String(80), nullable=False)
    parent_surface_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    business_domain: Mapped[str | None] = mapped_column(String(120), nullable=True)
    object_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    object_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(60), index=True, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    state_matrix: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    api_refs: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    review_gate_record_id: Mapped[str | None] = mapped_column(
        String(120), ForeignKey("review_gate_records.id"), index=True, nullable=True
    )
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class PageViewState(Base, TimestampMixin):
    __tablename__ = "page_view_states"
    __table_args__ = (
        Index("ix_page_view_states_object_ref", "object_type", "object_id"),
        Index("ix_page_view_states_created_at", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(80), ForeignKey("tenants.id"), index=True, nullable=False)
    case_id: Mapped[str | None] = mapped_column(String(80), ForeignKey("cases.id"), index=True, nullable=True)
    surface_contract_id: Mapped[str | None] = mapped_column(
        String(120), ForeignKey("page_surface_contracts.id"), index=True, nullable=True
    )
    surface_id: Mapped[str] = mapped_column(String(160), index=True, nullable=False)
    route: Mapped[str] = mapped_column(String(240), nullable=False)
    user_id: Mapped[str | None] = mapped_column(String(100), ForeignKey("users.id"), index=True, nullable=True)
    object_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    object_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(60), index=True, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    view_state: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    selected_refs: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    review_gate_record_id: Mapped[str | None] = mapped_column(
        String(120), ForeignKey("review_gate_records.id"), index=True, nullable=True
    )
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class BrowserVerificationRecord(Base, TimestampMixin):
    __tablename__ = "browser_verification_records"
    __table_args__ = (Index("ix_browser_verification_records_created_at", "created_at"),)

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(80), ForeignKey("tenants.id"), index=True, nullable=False)
    case_id: Mapped[str | None] = mapped_column(String(80), ForeignKey("cases.id"), index=True, nullable=True)
    surface_contract_id: Mapped[str | None] = mapped_column(
        String(120), ForeignKey("page_surface_contracts.id"), index=True, nullable=True
    )
    surface_id: Mapped[str] = mapped_column(String(160), index=True, nullable=False)
    route: Mapped[str] = mapped_column(String(240), nullable=False)
    test_id: Mapped[str] = mapped_column(String(120), nullable=False)
    viewport: Mapped[str | None] = mapped_column(String(80), nullable=True)
    status: Mapped[str] = mapped_column(String(60), index=True, nullable=False)
    result: Mapped[str] = mapped_column(String(60), nullable=False)
    screenshot_uri: Mapped[str | None] = mapped_column(String(500), nullable=True)
    network_log_refs: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    console_log_refs: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    evidence_refs: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    review_gate_record_id: Mapped[str | None] = mapped_column(
        String(120), ForeignKey("review_gate_records.id"), index=True, nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class BusinessCapabilityContract(Base, TimestampMixin):
    __tablename__ = "business_capability_contracts"
    __table_args__ = (Index("ix_business_capability_contracts_created_at", "created_at"),)

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(80), ForeignKey("tenants.id"), index=True, nullable=False)
    case_id: Mapped[str | None] = mapped_column(String(80), ForeignKey("cases.id"), index=True, nullable=True)
    capability_code: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    business_domain: Mapped[str] = mapped_column(String(120), nullable=False)
    business_object_type: Mapped[str] = mapped_column(String(80), nullable=False)
    owner: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(60), index=True, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    actions: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    input_schema: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    output_schema: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    review_gate_record_id: Mapped[str | None] = mapped_column(
        String(120), ForeignKey("review_gate_records.id"), index=True, nullable=True
    )
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class BusinessStateMachine(Base, TimestampMixin):
    __tablename__ = "business_state_machines"
    __table_args__ = (Index("ix_business_state_machines_created_at", "created_at"),)

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(80), ForeignKey("tenants.id"), index=True, nullable=False)
    case_id: Mapped[str | None] = mapped_column(String(80), ForeignKey("cases.id"), index=True, nullable=True)
    capability_contract_id: Mapped[str | None] = mapped_column(
        String(120), ForeignKey("business_capability_contracts.id"), index=True, nullable=True
    )
    object_type: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    initial_state: Mapped[str] = mapped_column(String(60), nullable=False)
    status: Mapped[str] = mapped_column(String(60), index=True, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    states: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    transitions: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    terminal_states: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    review_gate_record_id: Mapped[str | None] = mapped_column(
        String(120), ForeignKey("review_gate_records.id"), index=True, nullable=True
    )
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class BusinessFlowEdge(Base, TimestampMixin):
    __tablename__ = "business_flow_edges"
    __table_args__ = (
        Index("ix_business_flow_edges_from_object_ref", "from_object_type", "from_object_id"),
        Index("ix_business_flow_edges_to_object_ref", "to_object_type", "to_object_id"),
        Index("ix_business_flow_edges_created_at", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(80), ForeignKey("tenants.id"), index=True, nullable=False)
    case_id: Mapped[str | None] = mapped_column(String(80), ForeignKey("cases.id"), index=True, nullable=True)
    capability_contract_id: Mapped[str | None] = mapped_column(
        String(120), ForeignKey("business_capability_contracts.id"), index=True, nullable=True
    )
    flow_code: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    from_object_type: Mapped[str] = mapped_column(String(80), nullable=False)
    from_object_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    to_object_type: Mapped[str] = mapped_column(String(80), nullable=False)
    to_object_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    relation: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(60), index=True, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    blocker_conditions: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    input_refs: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    output_refs: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    review_gate_record_id: Mapped[str | None] = mapped_column(
        String(120), ForeignKey("review_gate_records.id"), index=True, nullable=True
    )
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class DecisionPoint(Base, TimestampMixin):
    __tablename__ = "decision_points"
    __table_args__ = (
        Index("ix_decision_points_object_ref", "object_type", "object_id"),
        Index("ix_decision_points_created_at", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(80), ForeignKey("tenants.id"), index=True, nullable=False)
    case_id: Mapped[str | None] = mapped_column(String(80), ForeignKey("cases.id"), index=True, nullable=True)
    capability_contract_id: Mapped[str | None] = mapped_column(
        String(120), ForeignKey("business_capability_contracts.id"), index=True, nullable=True
    )
    decision_code: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    object_type: Mapped[str] = mapped_column(String(80), nullable=False)
    object_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    actor_role: Mapped[str | None] = mapped_column(String(120), nullable=True)
    required_permission: Mapped[str | None] = mapped_column(String(120), nullable=True)
    reason_required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    evidence_required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    status: Mapped[str] = mapped_column(String(60), index=True, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    evidence_refs: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    review_gate_record_id: Mapped[str | None] = mapped_column(
        String(120), ForeignKey("review_gate_records.id"), index=True, nullable=True
    )
    audit_log_id: Mapped[str | None] = mapped_column(String(120), ForeignKey("audit_logs.id"), nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class WriteBackPoint(Base, TimestampMixin):
    __tablename__ = "write_back_points"
    __table_args__ = (
        Index("ix_write_back_points_source_object_ref", "source_object_type", "source_object_id"),
        Index("ix_write_back_points_target_object_ref", "target_object_type", "target_object_id"),
        Index("ix_write_back_points_created_at", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(80), ForeignKey("tenants.id"), index=True, nullable=False)
    case_id: Mapped[str | None] = mapped_column(String(80), ForeignKey("cases.id"), index=True, nullable=True)
    capability_contract_id: Mapped[str | None] = mapped_column(
        String(120), ForeignKey("business_capability_contracts.id"), index=True, nullable=True
    )
    point_code: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    source_object_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    source_object_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    target_object_type: Mapped[str] = mapped_column(String(80), nullable=False)
    target_object_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    target_table: Mapped[str] = mapped_column(String(120), nullable=False)
    version_strategy: Mapped[str] = mapped_column(String(80), nullable=False)
    conflict_strategy: Mapped[str] = mapped_column(String(80), nullable=False)
    rollback_strategy: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(60), index=True, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    review_gate_record_id: Mapped[str | None] = mapped_column(
        String(120), ForeignKey("review_gate_records.id"), index=True, nullable=True
    )
    audit_log_id: Mapped[str | None] = mapped_column(String(120), ForeignKey("audit_logs.id"), nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class BusinessQualityGate(Base, TimestampMixin):
    __tablename__ = "business_quality_gates"
    __table_args__ = (
        Index("ix_business_quality_gates_object_ref", "object_type", "object_id"),
        Index("ix_business_quality_gates_created_at", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(80), ForeignKey("tenants.id"), index=True, nullable=False)
    case_id: Mapped[str | None] = mapped_column(String(80), ForeignKey("cases.id"), index=True, nullable=True)
    gate_code: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    business_domain: Mapped[str] = mapped_column(String(120), nullable=False)
    object_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    object_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    gate_type: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(60), index=True, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    criteria: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    blocking_policy: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    evidence_refs: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    review_gate_record_id: Mapped[str | None] = mapped_column(
        String(120), ForeignKey("review_gate_records.id"), index=True, nullable=True
    )
    metrics_snapshot_id: Mapped[str | None] = mapped_column(String(120), ForeignKey("metrics_snapshots.id"), nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class FileObject(Base, TimestampMixin):
    __tablename__ = "file_objects"
    __table_args__ = (
        Index("ix_file_objects_object_ref", "object_type", "object_id"),
        Index("ix_file_objects_created_at", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(80), ForeignKey("tenants.id"), index=True, nullable=False)
    case_id: Mapped[str | None] = mapped_column(String(80), ForeignKey("cases.id"), index=True, nullable=True)
    owner_user_id: Mapped[str | None] = mapped_column(String(100), ForeignKey("users.id"), index=True, nullable=True)
    task_id: Mapped[str | None] = mapped_column(String(100), ForeignKey("tasks.id"), index=True, nullable=True)
    review_id: Mapped[str | None] = mapped_column(String(120), ForeignKey("reviews.id"), index=True, nullable=True)
    media_asset_id: Mapped[str | None] = mapped_column(String(120), ForeignKey("media_assets.id"), index=True, nullable=True)
    object_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    object_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    file_name: Mapped[str] = mapped_column(String(240), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(120), nullable=False)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    checksum: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(60), index=True, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    access_policy: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    source_refs: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    review_gate_record_id: Mapped[str | None] = mapped_column(
        String(120), ForeignKey("review_gate_records.id"), index=True, nullable=True
    )
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class Notification(Base, TimestampMixin):
    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notifications_source_object_ref", "source_object_type", "source_object_id"),
        Index("ix_notifications_created_at", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(80), ForeignKey("tenants.id"), index=True, nullable=False)
    case_id: Mapped[str | None] = mapped_column(String(80), ForeignKey("cases.id"), index=True, nullable=True)
    recipient_user_id: Mapped[str | None] = mapped_column(String(100), ForeignKey("users.id"), index=True, nullable=True)
    task_id: Mapped[str | None] = mapped_column(String(100), ForeignKey("tasks.id"), index=True, nullable=True)
    review_id: Mapped[str | None] = mapped_column(String(120), ForeignKey("reviews.id"), index=True, nullable=True)
    source_object_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    source_object_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    notification_type: Mapped[str] = mapped_column(String(80), nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(60), index=True, nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class AlgorithmRun(Base, TimestampMixin):
    __tablename__ = "algorithm_runs"
    __table_args__ = (
        Index("ix_algorithm_runs_object_ref", "object_type", "object_id"),
        Index("ix_algorithm_runs_created_at", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(80), ForeignKey("tenants.id"), index=True, nullable=False)
    case_id: Mapped[str | None] = mapped_column(String(80), ForeignKey("cases.id"), index=True, nullable=True)
    workflow_run_id: Mapped[str | None] = mapped_column(String(100), ForeignKey("workflow_runs.id"), index=True, nullable=True)
    config_version_id: Mapped[str | None] = mapped_column(String(120), ForeignKey("config_versions.id"), index=True, nullable=True)
    write_back_point_id: Mapped[str | None] = mapped_column(String(120), ForeignKey("write_back_points.id"), nullable=True)
    object_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    object_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    algorithm_name: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    algorithm_version: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(60), index=True, nullable=False)
    input_refs: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    output_refs: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    output: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    metrics: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(120), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    trace_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
