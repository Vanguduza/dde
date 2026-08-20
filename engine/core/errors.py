"""Typed error mapping to the Chapter 15.5 contract."""

from __future__ import annotations

from engine.contracts.error import Error
from engine.core.ids import uuid7


class DdeError(Exception):
    """Domain error that maps onto the gateway Error contract."""

    def __init__(
        self,
        error_code: str,
        message: str,
        *,
        retryable: bool = False,
        details: dict[str, object] | None = None,
        correlation_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.retryable = retryable
        self.details = details
        self.correlation_id = correlation_id or str(uuid7())

    def to_contract(self) -> Error:
        return Error(
            error_code=self.error_code,
            message=self.message,
            retryable=self.retryable,
            details=self.details,
            correlation_id=self.correlation_id,
        )
