"""Application-specific exception hierarchy for ГИС Красноярье."""

from __future__ import annotations


class AppError(Exception):
    """Base application error — all custom exceptions inherit from this."""

    def __init__(self, message: str, *, detail: object = None) -> None:
        self.message = message
        self.detail = detail
        super().__init__(message)


class NotFoundError(AppError):
    """Raised when a requested resource does not exist."""

    def __init__(self, entity: str, identifier: object) -> None:
        self.entity = entity
        self.identifier = identifier
        super().__init__(f"{entity} not found: {identifier}")


class PaymentError(AppError):
    """Raised when a payment-related operation fails."""


class NextGISError(AppError):
    """Raised when a NextGIS Web API call fails."""

    def __init__(self, message: str, *, status_code: int | None = None, response_body: str | None = None) -> None:
        self.status_code = status_code
        self.response_body = response_body
        super().__init__(message)


class YooKassaError(AppError):
    """Raised when a YooKassa API call fails."""

    def __init__(self, message: str, *, status_code: int | None = None, response_body: str | None = None) -> None:
        self.status_code = status_code
        self.response_body = response_body
        super().__init__(message)


class SubscriptionExpiredError(AppError):
    """Raised when a user tries to access a feature requiring an active subscription."""

    def __init__(self, message: str = "Your subscription has expired.") -> None:
        super().__init__(message)


class DailyLimitExceededError(AppError):
    """Raised when a user has exhausted their daily request limit."""

    def __init__(self, limit: int, *, message: str | None = None) -> None:
        self.limit = limit
        super().__init__(message or f"Daily limit of {limit} requests exceeded.")


class InvalidCadastralNumberError(AppError):
    """Raised when a cadastral number fails format/validation checks."""

    def __init__(self, cadastral_number: str, *, message: str | None = None) -> None:
        self.cadastral_number = cadastral_number
        super().__init__(message or f"Invalid cadastral number: {cadastral_number}")
