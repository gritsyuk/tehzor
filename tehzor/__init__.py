"""Асинхронный клиент Tehzor Public API."""

from ._registry import REGISTRY, Operation
from ._transport import PreparedRequest
from ._version import __version__
from .client import TehzorClient
from .errors import (
    BadRequestError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    QueryTooHeavyError,
    RateLimitError,
    ReadOnlyError,
    ServerError,
    ServiceUnavailableError,
    TehzorConnectionError,
    TehzorError,
    TehzorHTTPError,
    TehzorTimeoutError,
    UnauthorizedError,
)

__all__ = [
    "REGISTRY",
    "BadRequestError",
    "ConflictError",
    "ForbiddenError",
    "NotFoundError",
    "Operation",
    "PreparedRequest",
    "QueryTooHeavyError",
    "RateLimitError",
    "ReadOnlyError",
    "ServerError",
    "ServiceUnavailableError",
    "TehzorClient",
    "TehzorConnectionError",
    "TehzorError",
    "TehzorHTTPError",
    "TehzorTimeoutError",
    "UnauthorizedError",
    "__version__",
]
