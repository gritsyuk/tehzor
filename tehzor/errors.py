"""Иерархия исключений клиента."""

from __future__ import annotations


class TehzorError(Exception):
    """Базовое исключение библиотеки."""


class TehzorHTTPError(TehzorError):
    """API вернул код ответа >= 400."""

    def __init__(
        self,
        status: int,
        message: str,
        *,
        body: str | None = None,
        method: str | None = None,
        path: str | None = None,
        operation_id: str | None = None,
    ) -> None:
        self.status = status
        self.message = message
        self.body = body
        self.method = method
        self.path = path
        self.operation_id = operation_id
        where = f" {method} {path}" if method and path else ""
        super().__init__(f"HTTP {status}{where}: {message}")


class BadRequestError(TehzorHTTPError):
    """400 — неверные параметры запроса."""


class UnauthorizedError(TehzorHTTPError):
    """401 — не передан или неверен api-key."""


class ForbiddenError(TehzorHTTPError):
    """403 — нет доступа к ресурсу."""


class NotFoundError(TehzorHTTPError):
    """404 — ресурс не найден."""


class ConflictError(TehzorHTTPError):
    """409 — конфликт (например, при смене статуса помещения)."""


class RateLimitError(TehzorHTTPError):
    """429 — превышен лимит запросов."""


class ServerError(TehzorHTTPError):
    """5xx — ошибка на стороне сервера."""


class QueryTooHeavyError(ServerError):
    """502/504 после долгого ожидания: запрос слишком тяжёлый для сервера.

    Повтор того же запроса не поможет — нужно сузить фильтр (objects, даты) или уменьшить limit.
    """


class TehzorTimeoutError(TehzorError):
    """Истёк таймаут запроса или общий бюджет времени на вызов."""


class TehzorConnectionError(TehzorError):
    """Не удалось установить соединение с API."""


class ServiceUnavailableError(TehzorError):
    """Circuit breaker открыт: после серии сбоев запросы временно не отправляются."""

    def __init__(self, retry_after: float) -> None:
        self.retry_after = retry_after
        super().__init__(
            f"API временно недоступен после серии ошибок; запросы приостановлены на {retry_after:.0f} с"
        )


class ReadOnlyError(TehzorError):
    """Клиент работает в режиме только чтения, изменяющая операция запрещена."""


_STATUS_MAP: dict[int, type[TehzorHTTPError]] = {
    400: BadRequestError,
    401: UnauthorizedError,
    403: ForbiddenError,
    404: NotFoundError,
    409: ConflictError,
    429: RateLimitError,
}


def error_for_status(status: int) -> type[TehzorHTTPError]:
    """Класс исключения для HTTP-статуса."""
    if status in _STATUS_MAP:
        return _STATUS_MAP[status]
    if status >= 500:
        return ServerError
    return TehzorHTTPError
