"""Alembic migration script template."""

revision = "001"
down_revision = None
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


def upgrade() -> None:
    # users
    op.create_table(
        "users",
        sa.Column("telegram_id", sa.BigInteger(), autoincrement=False, nullable=False),
        sa.Column("username", sa.String(64), nullable=True),
        sa.Column("full_name", sa.String(128), nullable=True),
        sa.Column("role", sa.String(16), server_default="free", nullable=False),
        sa.Column("daily_requests_used", sa.Integer(), server_default="0", nullable=False),
        sa.Column("daily_requests_date", sa.Date(), nullable=True),
        sa.Column("is_blocked", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("registered_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("telegram_id"),
    )

    # payments
    op.create_table(
        "payments",
        sa.Column("id", postgresql.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("provider", sa.String(32), server_default="yookassa", nullable=False),
        sa.Column("plan_code", sa.String(64), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(8), server_default="RUB", nullable=False),
        sa.Column("status", sa.String(32), server_default="pending", nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("external_payment_id", sa.String(128), nullable=True),
        sa.Column("confirmation_url", sa.Text(), nullable=True),
        sa.Column("provider_payload", postgresql.JSONB(), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["telegram_id"], ["users.telegram_id"],),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
        sa.UniqueConstraint("external_payment_id"),
    )
    op.create_index("idx_payments_telegram_id", "payments", ["telegram_id"])
    op.create_index("idx_payments_status", "payments", ["status"])

    # payment_webhook_events
    op.create_table(
        "payment_webhook_events",
        sa.Column("id", postgresql.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("provider", sa.String(32), server_default="yookassa", nullable=False),
        sa.Column("external_event_id", sa.String(128), nullable=True),
        sa.Column("external_payment_id", sa.String(128), nullable=True),
        sa.Column("event_type", sa.String(128), nullable=True),
        sa.Column("event_hash", sa.String(128), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=True),
        sa.Column("processing_status", sa.String(32), server_default="received", nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "event_hash"),
    )
    op.create_index("idx_weh_external_payment_id", "payment_webhook_events", ["external_payment_id"])

    # subscriptions
    op.create_table(
        "subscriptions",
        sa.Column("id", postgresql.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("plan_code", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), server_default="active", nullable=False),
        sa.Column("payment_id", postgresql.UUID(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["telegram_id"], ["users.telegram_id"],),
        sa.ForeignKeyConstraint(["payment_id"], ["payments.id"],),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_subscriptions_telegram_id", "subscriptions", ["telegram_id"])
    op.create_index("idx_subscriptions_expires", "subscriptions", ["expires_at"])

    # tracked_objects
    op.create_table(
        "tracked_objects",
        sa.Column("id", postgresql.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("cadastral_number", sa.String(64), nullable=False),
        sa.Column("active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("last_snapshot_hash", sa.String(128), nullable=True),
        sa.Column("last_snapshot_payload", postgresql.JSONB(), nullable=True),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_notified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("telegram_id", "cadastral_number"),
    )
    op.create_index("idx_to_telegram_id", "tracked_objects", ["telegram_id"])
    op.create_index("idx_to_cadastral_number", "tracked_objects", ["cadastral_number"])

    # batch_jobs
    op.create_table(
        "batch_jobs",
        sa.Column("id", postgresql.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(32), server_default="uploaded", nullable=False),
        sa.Column("source_file_path", sa.Text(), nullable=True),
        sa.Column("result_file_path", sa.Text(), nullable=True),
        sa.Column("total_rows", sa.Integer(), server_default="0", nullable=False),
        sa.Column("processed_rows", sa.Integer(), server_default="0", nullable=False),
        sa.Column("success_rows", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_rows", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_bj_telegram_id", "batch_jobs", ["telegram_id"])

    # batch_items
    op.create_table(
        "batch_items",
        sa.Column("id", postgresql.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("batch_job_id", postgresql.UUID(), nullable=False),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("input_value", sa.Text(), nullable=False),
        sa.Column("normalized_cadnum", sa.String(64), nullable=True),
        sa.Column("status", sa.String(32), server_default="invalid_format", nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("result_json", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["batch_job_id"], ["batch_jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_bi_batch_job_id", "batch_items", ["batch_job_id"])

    # layer_sync_state
    op.create_table(
        "layer_sync_state",
        sa.Column("layer_key", sa.String(128), nullable=False),
        sa.Column("ngw_resource_id", sa.Integer(), nullable=False),
        sa.Column("last_seen_version", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_full_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(32), server_default="active", nullable=False),
        sa.Column("meta", postgresql.JSONB(), nullable=True),
        sa.PrimaryKeyConstraint("layer_key"),
        sa.UniqueConstraint("ngw_resource_id"),
    )

    # change_events
    op.create_table(
        "change_events",
        sa.Column("id", postgresql.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tracked_object_id", postgresql.UUID(), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("old_values", postgresql.JSONB(), nullable=True),
        sa.Column("new_values", postgresql.JSONB(), nullable=True),
        sa.Column("detected_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tracked_object_id"], ["tracked_objects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # notifications
    op.create_table(
        "notifications",
        sa.Column("id", postgresql.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("change_event_id", postgresql.UUID(), nullable=False),
        sa.Column("status", sa.String(32), server_default="pending", nullable=False),
        sa.Column("message_text", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["change_event_id"], ["change_events.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_notif_status", "notifications", ["status"])


def downgrade() -> None:
    op.drop_table("notifications")
    op.drop_table("change_events")
    op.drop_table("layer_sync_state")
    op.drop_table("batch_items")
    op.drop_table("batch_jobs")
    op.drop_table("tracked_objects")
    op.drop_table("subscriptions")
    op.drop_table("payment_webhook_events")
    op.drop_table("payments")
    op.drop_table("users")
