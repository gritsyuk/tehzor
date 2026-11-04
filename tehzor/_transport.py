"""HTTP-транспорт: единственное место, где библиотека обращается к API.

Правила защиты сервера (docs/DEVELOPMENT_PLAN.md, §2a):

* таймауты: соединение 10 с, весь запрос 35 с (чуть больше лимита шлюза ~30 с);
* ограничение частоты (token bucket) и параллельности (семафор);
* повторы только для безопасных операций, не больше `retries`, с экспоненциальной паузой,
  с учётом Retry-After и общим бюджетом времени на вызов;
* создание (неидемпотентная запись) никогда не повторяется после отправки запроса;
* 502/504 после долгого ожидания → QueryTooHeavyError без повтора;
* circuit breaker: после серии сбоев запросы временно не отправляются;
* 4xx не повторяются (кроме 429);
* режим только чтения: изменяющие операции блокируются до отправки.
"""

from __future__ import annotations

import asyncio
import json as jsonlib
import logging
import random
import ssl as ssllib
import time
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.parse import quote

import aiohttp

from ._registry import Operation
from ._version import __version__
from .errors import (
    QueryTooHeavyError,
    ReadOnlyError,
    ServiceUnavailableError,
    TehzorConnectionError,
    TehzorError,
    TehzorTimeoutError,
    error_for_status,
)
from .types import to_millis

logger = logging.getLogger("tehzor")

DEFAULT_BASE_URL = "https://api.tehzor.ru"
RETRYABLE_STATUSES = frozenset({429, 502, 503, 504})
HEAVY_STATUSES = frozenset({502, 504})
MAX_ERROR_BODY = 2000

Clock = Callable[[], float]
Sleep = Callable[[float], Awaitable[None]]

QueryValue = Any


@dataclass(frozen=True)
class PreparedRequest:
    """Запрос, подготовленный к отправке (dry_run, превью в MCP)."""

    method: str
    path: str
    params: tuple[tuple[str, str], ...]
    json: Any
    operation_id: str
    kind: str

    def describe(self) -> str:
        query = "&".join(f"{k}={v}" for k, v in self.params)
        return f"{self.method} {self.path}{'?' + query if query else ''}"


class RateLimiter:
    """Token bucket: не больше `rate` запросов в секунду (с запасом `burst`)."""

    def __init__(self, rate: float, *, burst: float | None = None, clock: Clock, sleep: Sleep) -> None:
        self.rate = rate
        self.burst = burst if burst is not None else max(1.0, rate)
        self._tokens = self.burst
        self._clock = clock
        self._sleep = sleep
        self._last = clock()
        self._lock: asyncio.Lock | None = None

    async def acquire(self) -> None:
        if self.rate <= 0:
            return
        if self._lock is None:
            self._lock = asyncio.Lock()
        async with self._lock:
            while True:
                now = self._clock()
                self._tokens = min(self.burst, self._tokens + (now - self._last) * self.rate)
                self._last = now
                if self._tokens >= 1:
                    self._tokens -= 1
                    return
                await self._sleep((1 - self._tokens) / self.rate)


class CircuitBreaker:
    """После `threshold` сбоев подряд запросы не отправляются `cooldown` секунд.

    Затем пропускается один пробный запрос (half-open): успех закрывает breaker, сбой открывает снова.
    `threshold <= 0` отключает breaker.
    """

    def __init__(self, threshold: int, cooldown: float, *, clock: Clock) -> None:
        self.threshold = threshold
        self.cooldown = cooldown
        self._clock = clock
        self._failures = 0
        self._opened_at: float | None = None
        self._trial_in_flight = False

    @property
    def is_open(self) -> bool:
        return self._opened_at is not None

    def before_request(self) -> None:
        if self.threshold <= 0 or self._opened_at is None:
            return
        elapsed = self._clock() - self._opened_at
        if elapsed < self.cooldown:
            raise ServiceUnavailableError(self.cooldown - elapsed)
        if self._trial_in_flight:
            raise ServiceUnavailableError(1.0)
        self._trial_in_flight = True

    def record_success(self) -> None:
        self._failures = 0
        self._opened_at = None
        self._trial_in_flight = False

    def record_failure(self) -> None:
        if self.threshold <= 0:
            return
        self._failures += 1
        if self._trial_in_flight or self._failures >= self.threshold:
            if self._opened_at is None or self._trial_in_flight:
                logger.warning("tehzor: circuit breaker открыт на %.0f с после %d сбоев", self.cooldown,
                               self._failures)
            self._opened_at = self._clock()
            self._trial_in_flight = False


def encode_query(params: Mapping[str, QueryValue] | None) -> tuple[tuple[str, str], ...]:
    """Query-параметры: None пропускается, списки раскрываются (fields=a&fields=b), bool → true/false."""
    if not params:
        return ()
    items: list[tuple[str, str]] = []

    def one(value: QueryValue) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, datetime):
            return str(to_millis(value))
        return str(getattr(value, "value", value))

    for key, value in params.items():
        if value is None:
            continue
        if isinstance(value, (list, tuple, set, frozenset)):
            items.extend((key, one(v)) for v in value if v is not None)
        else:
            items.append((key, one(value)))
    return tuple(items)


def format_path(template: str, path_params: Mapping[str, Any] | None) -> str:
    params = dict(path_params or {})
    try:
        return template.format(**{k: quote(str(v), safe="") for k, v in params.items()})
    except KeyError as exc:
        raise ValueError(f"Не передан параметр пути {exc} для {template}") from None


class Transport:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
        *,
        proxy: str | None = None,
        ssl: bool | ssllib.SSLContext = True,
        timeout: float = 35.0,
        connect_timeout: float = 10.0,
        max_concurrency: int = 5,
        rate_limit: float = 5.0,
        retries: int = 2,
        retry_budget: float = 60.0,
        backoff_base: float = 0.5,
        heavy_threshold: float = 25.0,
        breaker_threshold: int = 5,
        breaker_cooldown: float = 30.0,
        read_only: bool = False,
        trust_env: bool = True,
        clock: Clock = time.monotonic,
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.proxy = proxy
        self.ssl = ssl
        self.timeout = timeout
        self.connect_timeout = connect_timeout
        self.retries = max(0, retries)
        self.retry_budget = retry_budget
        self.backoff_base = backoff_base
        self.heavy_threshold = heavy_threshold
        self.read_only = read_only
        self.trust_env = trust_env
        self._api_key = api_key
        self._clock = clock
        self._sleep = sleep
        self._semaphore = asyncio.Semaphore(max(1, max_concurrency))
        self._max_concurrency = max(1, max_concurrency)
        self.rate_limiter = RateLimiter(rate_limit, clock=clock, sleep=sleep)
        self.breaker = CircuitBreaker(breaker_threshold, breaker_cooldown, clock=clock)
        self._session: aiohttp.ClientSession | None = None

    # --- жизненный цикл ---------------------------------------------------------------------

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "User-Agent": f"tehzor-python/{__version__}",
        }
        if self._api_key:
            headers["api-key"] = self._api_key
        return headers

    def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                base_url=self.base_url,
                headers=self._headers(),
                timeout=aiohttp.ClientTimeout(total=self.timeout, connect=self.connect_timeout),
                connector=aiohttp.TCPConnector(limit=self._max_concurrency * 2),
                # HTTP(S)_PROXY / NO_PROXY из окружения, как в requests и httpx
                trust_env=self.trust_env,
            )
        return self._session

    async def close(self) -> None:
        if self._session is not None and not self._session.closed:
            await self._session.close()
        self._session = None

    @property
    def closed(self) -> bool:
        return self._session is None or self._session.closed

    # --- запросы ----------------------------------------------------------------------------

    def prepare(
        self,
        op: Operation,
        *,
        path_params: Mapping[str, Any] | None = None,
        params: Mapping[str, QueryValue] | None = None,
        json: Any = None,
    ) -> PreparedRequest:
        return PreparedRequest(
            method=op.method,
            path=format_path(op.path, path_params),
            params=encode_query(params),
            json=json,
            operation_id=op.operation_id,
            kind=op.kind,
        )

    async def execute(
        self,
        op: Operation,
        *,
        path_params: Mapping[str, Any] | None = None,
        params: Mapping[str, QueryValue] | None = None,
        json: Any = None,
    ) -> Any:
        if op.mutating and self.read_only:
            raise ReadOnlyError(
                f"{op.tool_name or op.operation_id}: клиент в режиме только чтения, "
                f"операция {op.method} {op.path} не отправлена"
            )
        return await self.send(self.prepare(op, path_params=path_params, params=params, json=json),
                               can_retry=op.idempotent)

    async def send(self, req: PreparedRequest, *, can_retry: bool) -> Any:
        deadline = self._clock() + self.retry_budget
        attempt = 0
        while True:
            self.breaker.before_request()
            await self.rate_limiter.acquire()
            started = self._clock()
            try:
                async with self._semaphore:
                    status, headers, body = await self._raw(req)
            except aiohttp.ClientConnectorError as exc:
                # Соединение не установлено — запрос не ушёл, повтор безопасен даже для создания.
                self.breaker.record_failure()
                if not await self._backoff(attempt, deadline, None):
                    raise TehzorConnectionError(f"Нет соединения с {self.base_url}: {exc}") from exc
                attempt += 1
                continue
            except asyncio.TimeoutError as exc:
                # Сервер не ответил за timeout: запрос тяжёлый или сервер перегружен — не повторяем.
                self.breaker.record_failure()
                raise TehzorTimeoutError(
                    f"{req.describe()}: нет ответа за {self.timeout:.0f} с. Сузьте фильтр или уменьшите limit."
                ) from exc
            except aiohttp.ClientError as exc:
                self.breaker.record_failure()
                if not can_retry or not await self._backoff(attempt, deadline, None):
                    raise TehzorConnectionError(f"{req.describe()}: {exc}") from exc
                attempt += 1
                continue

            elapsed = self._clock() - started
            logger.debug("tehzor: %s -> %s (%.2f с)", req.describe(), status, elapsed)

            if 200 <= status < 300:
                self.breaker.record_success()
                return _decode(body)

            text = body.decode("utf-8", "replace")[:MAX_ERROR_BODY]
            if status >= 500:
                self.breaker.record_failure()
            else:
                self.breaker.record_success()  # сервер жив и ответил осмысленно

            if status in HEAVY_STATUSES and elapsed >= self.heavy_threshold:
                raise QueryTooHeavyError(
                    status,
                    f"сервер не успел обработать запрос за {elapsed:.0f} с; повтор не поможет — "
                    "сузьте фильтр (objects, даты) или уменьшите limit",
                    body=text, method=req.method, path=req.path, operation_id=req.operation_id,
                )

            if status in RETRYABLE_STATUSES and can_retry:
                retry_after = _retry_after(headers.get("Retry-After"))
                if await self._backoff(attempt, deadline, retry_after):
                    logger.info("tehzor: %s -> %s, повтор %d/%d", req.describe(), status, attempt + 1,
                                self.retries)
                    attempt += 1
                    continue

            raise error_for_status(status)(
                status, _message(text), body=text, method=req.method, path=req.path,
                operation_id=req.operation_id,
            )

    async def _raw(self, req: PreparedRequest) -> tuple[int, Mapping[str, str], bytes]:
        session = self._get_session()
        kwargs: dict[str, Any] = {"params": list(req.params) or None, "proxy": self.proxy, "ssl": self.ssl}
        if req.json is not None:
            kwargs["json"] = req.json
        async with session.request(req.method, req.path, **kwargs) as resp:
            body = await resp.read()
            return resp.status, resp.headers, body

    async def _backoff(self, attempt: int, deadline: float, retry_after: float | None) -> bool:
        """Ждёт перед повтором. False — повторов больше нет (исчерпаны попытки или бюджет времени)."""
        if attempt >= self.retries:
            return False
        delay = retry_after if retry_after is not None else self.backoff_base * (2**attempt)
        delay += random.uniform(0, delay * 0.1)
        if self._clock() + delay > deadline:
            return False
        await self._sleep(delay)
        return True


def _decode(body: bytes) -> Any:
    if not body.strip():
        return None
    try:
        return jsonlib.loads(body)
    except ValueError:
        return body.decode("utf-8", "replace")


def _message(text: str) -> str:
    try:
        data = jsonlib.loads(text)
    except ValueError:
        return text[:200] or "пустой ответ"
    if isinstance(data, dict):
        msg = data.get("message") or data.get("error")
        if isinstance(msg, list):
            return "; ".join(map(str, msg))
        if msg:
            return str(msg)
    return text[:200]


def _retry_after(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        return None


__all__ = [
    "DEFAULT_BASE_URL",
    "CircuitBreaker",
    "PreparedRequest",
    "RateLimiter",
    "TehzorError",
    "Transport",
    "encode_query",
    "format_path",
]
