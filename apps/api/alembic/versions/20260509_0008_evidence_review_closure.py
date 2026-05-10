"""s4b evidence review closure schema

Revision ID: 20260509_0008
Revises: 20260509_0007
Create Date: 2026-05-09
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260509_0008"
down_revision = "20260509_0007"
branch_labels = None
depends_on = None


def _json_type():
    return sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def _json_default(bind):
    return sa.text("'{}'::jsonb") if bind.dialect.name == "postgresql" else sa.text("'{}'")


def upgrade() -> None:
    bind = op.get_bind()
    json_type = _json_type()
    json_default = _json_default(bind)

    op.create_table(
        "evidence_reviews",
        sa.Column("id", sa.String(length=120), primary_key=True),
        sa.Column("tenant_id", sa.String(length=80), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("case_id", sa.String(length=80), sa.ForeignKey("cases.id"), nullable=False),
        sa.Column("topic_id", sa.String(length=120), sa.ForeignKey("topics.id"), nullable=True),
        sa.Column("evidence_id", sa.String(length=100), sa.ForeignKey("evidence.id"), nullable=False),
        sa.Column("signal_id", sa.String(length=100), sa.ForeignKey("signals.id"), nullable=True),
        sa.Column("status", sa.String(length=60), nullable=False),
        sa.Column("reviewer_id", sa.String(length=100), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("decision", sa.String(length=80), nullable=True),
        sa.Column("payload", json_type, nullable=False, server_default=json_default),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_evidence_reviews_tenant_id", "evidence_reviews", ["tenant_id"])
    op.create_index("ix_evidence_reviews_case_id", "evidence_reviews", ["case_id"])
    op.create_index("ix_evidence_reviews_topic_id", "evidence_reviews", ["topic_id"])
    op.create_index("ix_evidence_reviews_evidence_id", "evidence_reviews", ["evidence_id"], unique=True)
    op.create_index("ix_evidence_reviews_signal_id", "evidence_reviews", ["signal_id"])

    op.create_table(
        "evidence_media_links",
        sa.Column("id", sa.String(length=120), primary_key=True),
        sa.Column("tenant_id", sa.String(length=80), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("evidence_id", sa.String(length=100), sa.ForeignKey("evidence.id"), nullable=False),
        sa.Column("media_asset_id", sa.String(length=120), sa.ForeignKey("media_assets.id"), nullable=False),
        sa.Column("relation", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=60), nullable=False),
        sa.Column("payload", json_type, nullable=False, server_default=json_default),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_evidence_media_links_tenant_id", "evidence_media_links", ["tenant_id"])
    op.create_index("ix_evidence_media_links_evidence_id", "evidence_media_links", ["evidence_id"])
    op.create_index("ix_evidence_media_links_media_asset_id", "evidence_media_links", ["media_asset_id"])
    op.create_index("ux_evidence_media_link", "evidence_media_links", ["evidence_id", "media_asset_id", "relation"], unique=True)


def downgrade() -> None:
    raise RuntimeError("Downgrade is intentionally disabled for S4B evidence review closure schema.")
