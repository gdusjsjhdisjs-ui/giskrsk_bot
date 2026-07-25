"""Domain enumerations for ГИС Красноярье Telegram bot."""

from __future__ import annotations

from enum import StrEnum


class UserRole(StrEnum):
    """User roles within the system."""

    FREE = "free"
    BASIC = "basic"
    PRO_30D = "pro_30d"
    PRO_90D = "pro_90d"
    YEAR = "year"
    ADMIN = "admin"


class PaymentStatus(StrEnum):
    """Status of a payment transaction."""

    PENDING = "pending"
    SUCCEEDED = "succeeded"
    CANCELED = "canceled"


class PlanCode(StrEnum):
    """Subscription plan identifiers."""

    BASIC_30D = "basic_30d"
    PRO_30D = "pro_30d"
    PRO_90D = "pro_90d"
    YEAR = "year"


class SubscriptionStatus(StrEnum):
    """Lifecycle status of a subscription."""

    ACTIVE = "active"
    EXPIRED = "expired"
    CANCELED = "canceled"


class BatchStatus(StrEnum):
    """Status of a batch processing job."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class BatchItemStatus(StrEnum):
    """Status of an individual item within a batch job."""

    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    ERROR = "error"


class WebhookEventStatus(StrEnum):
    """Processing status for incoming webhook events."""

    NEW = "new"
    PROCESSED = "processed"
    FAILED = "failed"
    IGNORED = "ignored"


class ChangeEventType(StrEnum):
    """Types of changes detected on tracked cadastral objects."""

    CREATED = "created"
    UPDATED = "updated"
    DELETED = "deleted"
    STATUS_CHANGED = "status_changed"
    OWNERSHIP_CHANGED = "ownership_changed"
    CATEGORY_CHANGED = "category_changed"
    PERMITTED_USE_CHANGED = "permitted_use_changed"
    AREA_CHANGED = "area_changed"
    PZZ_ZONE_CHANGED = "pzz_zone_changed"


class NotificationStatus(StrEnum):
    """Delivery status of a notification to a user."""

    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"


class LayerSyncStatus(StrEnum):
    """Synchronisation status for a NextGIS Web layer."""

    PENDING = "pending"
    SYNCING = "syncing"
    SYNCED = "synced"
    FAILED = "failed"
