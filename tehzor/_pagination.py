"""Автопагинация по limit/offset с защитой от тяжёлых запросов."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import TypeVar

from .errors import QueryTooHeavyError

T = TypeVar("T")

logger = logging.getLogger("tehzor")

DEFAULT_PAGE_SIZE = 50
"""Факт: 100 нарушений крупного объекта ≈ 15 с при лимите шлюза ~30 с (docs/API_FACTS.md)."""


async def iter_pages(
    fetch: Callable[[int, int], Awaitable[list[T]]],
    *,
    page_size: int = DEFAULT_PAGE_SIZE,
    max_items: int | None = None,
    offset: int = 0,
) -> AsyncIterator[T]:
    """Загружает страницы `fetch(limit, offset)`, пока очередная не окажется короче запрошенной.

    При QueryTooHeavyError размер страницы один раз уменьшается вдвое; повторная ошибка пробрасывается.
    """
    if page_size < 1:
        raise ValueError("page_size должен быть >= 1")
    size = page_size
    halved = False
    yielded = 0
    while True:
        limit = size if max_items is None else min(size, max_items - yielded)
        if limit <= 0:
            return
        try:
            page = await fetch(limit, offset)
        except QueryTooHeavyError:
            if halved or size <= 1:
                raise
            size = max(1, size // 2)
            halved = True
            logger.warning("tehzor: тяжёлый запрос, размер страницы уменьшен до %d", size)
            continue
        for item in page:
            yield item
            yielded += 1
        if len(page) < limit:
            return
        offset += len(page)
