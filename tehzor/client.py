"""TehzorClient — точка входа библиотеки."""

from __future__ import annotations

import os
import ssl as ssllib
from types import TracebackType

from ._transport import DEFAULT_BASE_URL, Transport
from .models.objects import HealthStatus
from .resources.objects import ObjectsResource, ServiceResource


class TehzorClient:
    """Асинхронный клиент Tehzor Public API.

    ```python
    async with TehzorClient(api_key="...") as thz:
        stages = await thz.objects.stages()
    ```

    `api_key` можно не передавать: тогда берётся переменная окружения `TEHZOR_API_KEY`, а если её нет,
    заголовок `api-key` не отправляется (например, когда его подставляет прокси).

    `read_only=True` блокирует все изменяющие операции до отправки запроса.
    Параметры защиты сервера описаны в docs/DEVELOPMENT_PLAN.md (§2a).
    """

    def __init__(
        self,
        api_key: str | None = None,
        *,
        user_id: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
        proxy: str | None = None,
        ssl: bool | ssllib.SSLContext = True,
        timeout: float = 35.0,
        connect_timeout: float = 10.0,
        max_concurrency: int = 5,
        rate_limit: float = 5.0,
        retries: int = 2,
        retry_budget: float = 60.0,
        heavy_threshold: float = 25.0,
        breaker_threshold: int = 5,
        breaker_cooldown: float = 30.0,
        read_only: bool = False,
        trust_env: bool = True,
        transport: Transport | None = None,
    ) -> None:
        if api_key is None:
            api_key = os.environ.get("TEHZOR_API_KEY") or None
        self.user_id = user_id
        self.transport = transport or Transport(
            api_key,
            base_url,
            proxy=proxy,
            ssl=ssl,
            timeout=timeout,
            connect_timeout=connect_timeout,
            max_concurrency=max_concurrency,
            rate_limit=rate_limit,
            retries=retries,
            retry_budget=retry_budget,
            heavy_threshold=heavy_threshold,
            breaker_threshold=breaker_threshold,
            breaker_cooldown=breaker_cooldown,
            read_only=read_only,
            trust_env=trust_env,
        )
        self.objects = ObjectsResource(self.transport)
        self._service = ServiceResource(self.transport)

    @property
    def read_only(self) -> bool:
        return self.transport.read_only

    async def health(self) -> HealthStatus:
        """`GET /health/readiness` — не описан в openapi.json, но существует."""
        return await self._service.health()

    async def close(self) -> None:
        await self.transport.close()

    async def __aenter__(self) -> TehzorClient:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.close()
