from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from typing import Any

import pytest
from aioresponses import aioresponses

from tehzor._transport import Transport

BASE = "https://api.tehzor.ru"


class FakeClock:
    """Управляемые часы: sleep не ждёт, а сдвигает время."""

    def __init__(self) -> None:
        self.t = 1000.0
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.t

    async def sleep(self, delay: float) -> None:
        self.sleeps.append(delay)
        self.t += delay

    def advance(self, seconds: float) -> None:
        self.t += seconds


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def mocked() -> Iterator[aioresponses]:
    # Без passthrough: любой незамоканный запрос падает — unit-тесты не могут уйти в сеть.
    with aioresponses() as m:
        yield m


@pytest.fixture
async def make_transport(clock: FakeClock) -> AsyncIterator[Any]:
    created: list[Transport] = []

    def factory(**kwargs: Any) -> Transport:
        params: dict[str, Any] = {"rate_limit": 0, "clock": clock, "sleep": clock.sleep}
        params.update(kwargs)
        t = Transport(**params)
        created.append(t)
        return t

    yield factory
    for t in created:
        await t.close()


def calls(m: aioresponses, method: str, url: str) -> list[Any]:
    """Список запросов к (method, url) без учёта query."""
    from yarl import URL

    found: list[Any] = []
    for (meth, u), reqs in m.requests.items():
        if meth == method and URL(str(u)).with_query(None) == URL(url):
            found.extend(reqs)
    return found
