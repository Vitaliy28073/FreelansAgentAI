"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-11-02
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("telegram_id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(64)),
        sa.Column("language", sa.String(8), server_default="ru"),
        sa.Column("timezone", sa.String(64), server_default="UTC"),
        sa.Column("paused", sa.Boolean(), server_default=sa.false()),
        sa.Column("full_monitoring", sa.Boolean(), server_default=sa.false()),
        sa.Column("notify_score_threshold", sa.Integer(), server_default="45"),
        sa.Column("max_notifications_per_day", sa.Integer(), server_default="30"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_users_telegram_id", "users", ["telegram_id"], unique=True)

    op.create_table(
        "freelancer_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("specialization", sa.String(255), server_default=""),
        sa.Column("skills", sa.JSON(), nullable=False),
        sa.Column("keywords", sa.JSON(), nullable=False),
        sa.Column("stop_words", sa.JSON(), nullable=False),
        sa.Column("excluded_categories", sa.JSON(), nullable=False),
        sa.Column("experience_level", sa.String(64), server_default=""),
        sa.Column("portfolio", sa.JSON(), nullable=False),
        sa.Column("availability", sa.String(255), server_default=""),
        sa.Column("languages", sa.JSON(), nullable=False),
        sa.Column("min_budget", sa.Float()),
        sa.Column("desired_rate", sa.Float()),
        sa.Column("currency", sa.String(8), server_default="RUB"),
        sa.Column("preferred_regions", sa.JSON(), nullable=False),
        sa.Column("project_types", sa.JSON(), nullable=False),
        sa.Column("unwanted_payment_types", sa.JSON(), nullable=False),
        sa.Column("tone", sa.String(64), server_default="professional"),
        sa.Column("sample_responses", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "source_connectors",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.false()),
        sa.Column("status", sa.String(64), server_default="disabled"),
        sa.Column("access_method", sa.String(32), server_default="rss"),
        sa.Column("cursor", sa.JSON(), nullable=False),
        sa.Column("last_success_at", sa.DateTime(timezone=True)),
        sa.Column("last_error", sa.Text()),
        sa.Column("last_error_code", sa.String(64)),
        sa.Column("rules_checked_at", sa.DateTime(timezone=True)),
        sa.Column("circuit_open_until", sa.DateTime(timezone=True)),
        sa.Column("consecutive_failures", sa.Integer(), server_default="0"),
        sa.UniqueConstraint("user_id", "code", name="uq_user_source"),
    )

    op.create_table(
        "source_credentials",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("connector_id", sa.Integer(), sa.ForeignKey("source_connectors.id"), nullable=False),
        sa.Column("encrypted_token", sa.Text(), server_default=""),
        sa.Column("token_hint", sa.String(16), server_default=""),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("external_id", sa.String(128), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("canonical_url", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), server_default=""),
        sa.Column("category", sa.String(255)),
        sa.Column("skills", sa.JSON(), nullable=False),
        sa.Column("budget_amount", sa.Float()),
        sa.Column("budget_currency", sa.String(8)),
        sa.Column("budget_raw", sa.String(255)),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("discovered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("bid_count", sa.Integer()),
        sa.Column("language", sa.String(8)),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("extras", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(32), server_default="new"),
        sa.UniqueConstraint("source", "external_id", name="uq_job_source_external"),
        sa.UniqueConstraint("canonical_url", name="uq_job_canonical_url"),
    )

    op.create_table(
        "job_sources",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id"), nullable=False),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("external_id", sa.String(128), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.UniqueConstraint("job_id", "source", "external_id", name="uq_job_source_link"),
    )

    op.create_table(
        "job_user_states",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id"), nullable=False),
        sa.Column("status", sa.String(32), server_default="new"),
        sa.Column("favorite", sa.Boolean(), server_default=sa.false()),
        sa.Column("filter_passed", sa.Boolean(), server_default=sa.false()),
        sa.Column("filter_reasons", sa.JSON(), nullable=False),
        sa.Column("notified_at", sa.DateTime(timezone=True)),
        sa.Column("telegram_chat_id", sa.Integer()),
        sa.Column("telegram_message_id", sa.Integer()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "job_id", name="uq_user_job"),
    )

    op.create_table(
        "job_analyses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("model", sa.String(128), nullable=False),
        sa.Column("summary", sa.Text(), server_default=""),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("score", sa.Integer(), server_default="0"),
        sa.Column("risk_penalty", sa.Integer(), server_default="0"),
        sa.Column("decision", sa.String(32), server_default="manual_review"),
        sa.Column("confidence", sa.Float(), server_default="0"),
        sa.Column("fallback", sa.Boolean(), server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "response_drafts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("style", sa.String(32), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("used_profile_facts", sa.JSON(), nullable=False),
        sa.Column("missing_facts", sa.JSON(), nullable=False),
        sa.Column("edited_body", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    for table in ("outreach_events", "feedback", "notification_events"):
        extra = []
        if table == "outreach_events":
            extra = [
                sa.Column("action", sa.String(64), nullable=False),
                sa.Column("payload", sa.JSON(), nullable=False),
            ]
        elif table == "feedback":
            extra = [
                sa.Column("relevant", sa.Boolean()),
                sa.Column("reason", sa.Text()),
            ]
        else:
            extra = [
                sa.Column("channel", sa.String(32), server_default="telegram"),
                sa.Column("status", sa.String(32), server_default="sent"),
                sa.Column("error", sa.Text()),
            ]
        op.create_table(
            table,
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id"), nullable=False),
            *extra,
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )

    op.create_table(
        "connector_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("connector_code", sa.String(64), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("fetched", sa.Integer(), server_default="0"),
        sa.Column("inserted", sa.Integer(), server_default="0"),
        sa.Column("duplicates", sa.Integer(), server_default="0"),
        sa.Column("filtered", sa.Integer(), server_default="0"),
        sa.Column("analyzed", sa.Integer(), server_default="0"),
        sa.Column("notified", sa.Integer(), server_default="0"),
        sa.Column("error", sa.Text()),
        sa.Column("error_code", sa.String(64)),
        sa.Column("correlation_id", sa.String(32), server_default=""),
    )

    op.create_table(
        "audit_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer()),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("detail", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    for table in [
        "audit_events",
        "connector_runs",
        "notification_events",
        "feedback",
        "outreach_events",
        "response_drafts",
        "job_analyses",
        "job_user_states",
        "job_sources",
        "jobs",
        "source_credentials",
        "source_connectors",
        "freelancer_profiles",
        "users",
    ]:
        op.drop_table(table)
