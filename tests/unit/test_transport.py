"""Транспорт: маппинг ошибок и правила защиты сервера (§2a плана). Только заглушки, без сети."""

from __future__ import annotations

import asyncio
import logging
from typing import Any
from unittest.mock import MagicMock

import aiohttp
import pytest
from aioresponses import aioresponses

from tehzor._registry import Operation
from tehzor._transport import CircuitBreaker, RateLimiter, encode_query, format_path
from tehzor.errors import (
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
    TehzorTimeoutError,
    UnauthorizedError,
)
from tests.conftest import BASE, FakeClock, calls

READ = Operation("Test_read", "GET", "/things/{id}", "R", resource="things", name="get")
LIST = Operation("Test_list", "POST", "/things/get-things", "R", resource="things", name="list")
CREATE = Operation("Test_create", "POST", "/things", "W", idempotent=False, resource="things", name="create")
EDIT = Operation("Test_edit", "POST", "/things/{id}", "W", idempotent=True, resource="things", name="edit")
DELETE = Operation("Test_delete", "DELETE", "/things/{id}/delete", "D", idempotent=False, resource="things",
                   name="delete")

URL1 = f"{BASE}/things/1"


# --- успешные ответы ---------------------------------------------------------------------------


@pytest.mark.parametrize("status", [200, 201])
async def test_2xx_is_success(make_transport: Any, mocked: aioresponses, status: int) -> None:
    mocked.get(URL1, status=status, payload={"id": "1"})
    t = make_transport()
    assert await t.execute(READ, path_params={"id": "1"}) == {"id": "1"}


async def test_empty_body_is_none(make_transport: Any, mocked: aioresponses) -> None:
    mocked.get(URL1, status=200, body=b"")
    assert await make_transport().execute(READ, path_params={"id": "1"}) is None


# --- маппинг ошибок ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("status", "exc"),
    [(400, BadRequestError), (401, UnauthorizedError), (403, ForbiddenError), (404, NotFoundError),
     (409, ConflictError), (500, ServerError)],
)
async def test_status_mapping(make_transport: Any, mocked: aioresponses, status: int, exc: type) -> None:
    mocked.get(URL1, status=status, payload={"message": "Нарушение не найдено", "statusCode": status})
    with pytest.raises(exc) as info:
        await make_transport().execute(READ, path_params={"id": "1"})
    assert info.value.status == status
    assert info.value.message == "Нарушение не найдено"
    assert info.value.path == "/things/1"
    assert len(calls(mocked, "GET", URL1)) == 1  # 4xx и 500 не повторяются


async def test_error_does_not_close_session(make_transport: Any, mocked: aioresponses) -> None:
    mocked.get(URL1, status=404, payload={})
    mocked.get(URL1, status=200, payload={"id": "1"})
    t = make_transport()
    with pytest.raises(NotFoundError):
        await t.execute(READ, path_params={"id": "1"})
    assert not t.closed
    assert await t.execute(READ, path_params={"id": "1"}) == {"id": "1"}


async def test_parallel_failure_does_not_break_others(make_transport: Any, mocked: aioresponses) -> None:
    mocked.get(f"{BASE}/things/bad", status=404, payload={})
    for i in range(3):
        mocked.get(f"{BASE}/things/{i}", status=200, payload={"id": str(i)})
    t = make_transport()
    results = await asyncio.gather(
        *(t.execute(READ, path_params={"id": x}) for x in ["0", "bad", "1", "2"]), return_exceptions=True
    )
    assert isinstance(results[1], NotFoundError)
    assert [r["id"] for r in results if isinstance(r, dict)] == ["0", "1", "2"]


# --- повторы ------------------------------------------------------------------------------------


async def test_retry_on_503_then_success(make_transport: Any, mocked: aioresponses, clock: FakeClock) -> None:
    mocked.get(URL1, status=503)
    mocked.get(URL1, status=200, payload={"id": "1"})
    assert await make_transport().execute(READ, path_params={"id": "1"}) == {"id": "1"}
    assert len(calls(mocked, "GET", URL1)) == 2
    assert 0.5 <= clock.sleeps[0] <= 0.55


async def test_retry_after_is_respected(make_transport: Any, mocked: aioresponses, clock: FakeClock) -> None:
    mocked.get(URL1, status=429, headers={"Retry-After": "3"})
    mocked.get(URL1, status=200, payload={})
    await make_transport().execute(READ, path_params={"id": "1"})
    assert 3.0 <= clock.sleeps[0] <= 3.3


async def test_retries_are_limited(make_transport: Any, mocked: aioresponses) -> None:
    for _ in range(5):
        mocked.get(URL1, status=503)
    with pytest.raises(ServerError):
        await make_transport(retries=2).execute(READ, path_params={"id": "1"})
    assert len(calls(mocked, "GET", URL1)) == 3  # 1 + 2 повтора


async def test_429_exhausted_raises_rate_limit(make_transport: Any, mocked: aioresponses) -> None:
    for _ in range(3):
        mocked.get(URL1, status=429)
    with pytest.raises(RateLimitError):
        await make_transport(retries=2).execute(READ, path_params={"id": "1"})


async def test_retry_budget_stops_retries(make_transport: Any, mocked: aioresponses) -> None:
    for _ in range(5):
        mocked.get(URL1, status=503)
    with pytest.raises(ServerError):
        # пауза 0.5 с влезает в бюджет 1 с, следующая (1 с) — уже нет
        await make_transport(retries=5, retry_budget=1.0).execute(READ, path_params={"id": "1"})
    assert len(calls(mocked, "GET", URL1)) == 2


async def test_create_is_never_retried(make_transport: Any, mocked: aioresponses) -> None:
    mocked.post(f"{BASE}/things", status=503)
    mocked.post(f"{BASE}/things", status=201, payload={"id": "dup"})
    with pytest.raises(ServerError):
        await make_transport().execute(CREATE, json={"name": "x"})
    assert len(calls(mocked, "POST", f"{BASE}/things")) == 1


async def test_idempotent_edit_is_retried(make_transport: Any, mocked: aioresponses) -> None:
    mocked.post(URL1, status=503)
    mocked.post(URL1, status=200, payload={"id": "1"})
    assert await make_transport().execute(EDIT, path_params={"id": "1"}, json={}) == {"id": "1"}


async def test_connection_error_retried_even_for_create(make_transport: Any, mocked: aioresponses) -> None:
    err = aiohttp.ClientConnectorError(MagicMock(), OSError("connection refused"))
    mocked.post(f"{BASE}/things", exception=err)
    mocked.post(f"{BASE}/things", status=201, payload={"id": "new"})
    # Соединение не установлено → запрос не ушёл → повтор не создаст дубль.
    assert await make_transport().execute(CREATE, json={}) == {"id": "new"}


async def test_connection_error_exhausted(make_transport: Any, mocked: aioresponses) -> None:
    err = aiohttp.ClientConnectorError(MagicMock(), OSError("connection refused"))
    for _ in range(3):
        mocked.get(URL1, exception=err)
    with pytest.raises(TehzorConnectionError):
        await make_transport().execute(READ, path_params={"id": "1"})


async def test_timeout_is_not_retried(make_transport: Any, mocked: aioresponses) -> None:
    mocked.get(URL1, exception=asyncio.TimeoutError())
    mocked.get(URL1, status=200, payload={})
    with pytest.raises(TehzorTimeoutError):
        await make_transport().execute(READ, path_params={"id": "1"})
    assert len(calls(mocked, "GET", URL1)) == 1


# --- тяжёлые запросы ----------------------------------------------------------------------------


async def test_slow_502_is_heavy_and_not_retried(make_transport: Any, mocked: aioresponses) -> None:
    mocked.post(f"{BASE}/things/get-things", status=502)
    mocked.post(f"{BASE}/things/get-things", status=200, payload=[])
    with pytest.raises(QueryTooHeavyError) as info:
        await make_transport(heavy_threshold=0).execute(LIST)
    assert "сузьте фильтр" in info.value.message
    assert len(calls(mocked, "POST", f"{BASE}/things/get-things")) == 1


async def test_fast_502_is_retried(make_transport: Any, mocked: aioresponses) -> None:
    mocked.post(f"{BASE}/things/get-things", status=502)
    mocked.post(f"{BASE}/things/get-things", status=200, payload=[])
    assert await make_transport(heavy_threshold=25).execute(LIST) == []


# --- circuit breaker ----------------------------------------------------------------------------


async def test_breaker_opens_and_blocks(make_transport: Any, mocked: aioresponses, clock: FakeClock) -> None:
    for _ in range(2):
        mocked.get(URL1, status=500)
    t = make_transport(breaker_threshold=2, breaker_cooldown=30)
    for _ in range(2):
        with pytest.raises(ServerError):
            await t.execute(READ, path_params={"id": "1"})
    with pytest.raises(ServiceUnavailableError) as info:
        await t.execute(READ, path_params={"id": "1"})
    assert info.value.retry_after == pytest.approx(30)
    assert len(calls(mocked, "GET", URL1)) == 2  # третий запрос не ушёл

    clock.advance(31)
    mocked.get(URL1, status=200, payload={"id": "1"})
    assert await t.execute(READ, path_params={"id": "1"}) == {"id": "1"}  # пробный запрос
    assert not t.breaker.is_open


async def test_breaker_half_open_failure_reopens(make_transport: Any, mocked: aioresponses,
                                                 clock: FakeClock) -> None:
    for _ in range(3):
        mocked.get(URL1, status=500)
    t = make_transport(breaker_threshold=2, breaker_cooldown=30)
    for _ in range(2):
        with pytest.raises(ServerError):
            await t.execute(READ, path_params={"id": "1"})
    clock.advance(31)
    with pytest.raises(ServerError):
        await t.execute(READ, path_params={"id": "1"})
    with pytest.raises(ServiceUnavailableError):
        await t.execute(READ, path_params={"id": "1"})


async def test_4xx_resets_breaker(make_transport: Any, mocked: aioresponses) -> None:
    mocked.get(URL1, status=500)
    mocked.get(URL1, status=404, payload={})
    mocked.get(URL1, status=500)
    t = make_transport(breaker_threshold=2)
    for exc in (ServerError, NotFoundError, ServerError):
        with pytest.raises(exc):
            await t.execute(READ, path_params={"id": "1"})
    assert not t.breaker.is_open


def test_breaker_disabled() -> None:
    b = CircuitBreaker(0, 30, clock=lambda: 0.0)
    for _ in range(10):
        b.record_failure()
    b.before_request()
    assert not b.is_open


# --- ограничение частоты ------------------------------------------------------------------------


async def test_rate_limiter(clock: FakeClock) -> None:
    limiter = RateLimiter(2.0, burst=2, clock=clock, sleep=clock.sleep)
    for _ in range(6):
        await limiter.acquire()
    # 2 запроса из запаса, ещё 4 — по 0.5 с
    assert sum(clock.sleeps) == pytest.approx(2.0)


async def test_rate_limit_applies_to_requests(make_transport: Any, mocked: aioresponses,
                                              clock: FakeClock) -> None:
    for _ in range(3):
        mocked.get(URL1, status=200, payload={})
    t = make_transport(rate_limit=1.0)
    for _ in range(3):
        await t.execute(READ, path_params={"id": "1"})
    assert sum(clock.sleeps) == pytest.approx(2.0)


# --- только чтение ------------------------------------------------------------------------------


@pytest.mark.parametrize("op", [CREATE, EDIT, DELETE])
async def test_read_only_blocks_mutations_before_network(make_transport: Any, mocked: aioresponses,
                                                         op: Operation) -> None:
    with pytest.raises(ReadOnlyError):
        await make_transport(read_only=True).execute(op, path_params={"id": "1"}, json={})
    assert not mocked.requests


async def test_read_only_allows_reads(make_transport: Any, mocked: aioresponses) -> None:
    mocked.get(URL1, status=200, payload={})
    await make_transport(read_only=True).execute(READ, path_params={"id": "1"})


# --- заголовки, ssl, proxy, логи ----------------------------------------------------------------


async def test_api_key_header(make_transport: Any, mocked: aioresponses) -> None:
    mocked.get(URL1, status=200, payload={})
    t = make_transport(api_key="secret-key")
    await t.execute(READ, path_params={"id": "1"})
    assert t._get_session().headers["api-key"] == "secret-key"


async def test_no_api_key_header_when_absent(make_transport: Any, mocked: aioresponses) -> None:
    mocked.get(URL1, status=200, payload={})
    t = make_transport(api_key=None)
    await t.execute(READ, path_params={"id": "1"})
    assert "api-key" not in t._get_session().headers


async def test_ssl_and_proxy_passed(make_transport: Any, mocked: aioresponses) -> None:
    mocked.get(URL1, status=200, payload={})
    await make_transport(ssl=False, proxy="http://proxy:8080").execute(READ, path_params={"id": "1"})
    kwargs = calls(mocked, "GET", URL1)[0].kwargs
    assert kwargs["ssl"] is False
    assert kwargs["proxy"] == "http://proxy:8080"


async def test_ssl_verified_by_default(make_transport: Any, mocked: aioresponses) -> None:
    mocked.get(URL1, status=200, payload={})
    await make_transport().execute(READ, path_params={"id": "1"})
    assert calls(mocked, "GET", URL1)[0].kwargs["ssl"] is True


async def test_api_key_not_logged(make_transport: Any, mocked: aioresponses,
                                  caplog: pytest.LogCaptureFixture) -> None:
    mocked.get(URL1, status=503)
    mocked.get(URL1, status=404, payload={"message": "nope"})
    caplog.set_level(logging.DEBUG, logger="tehzor")
    with pytest.raises(NotFoundError) as info:
        await make_transport(api_key="secret-key").execute(READ, path_params={"id": "1"})
    assert caplog.records
    assert "secret-key" not in caplog.text
    assert "secret-key" not in str(info.value)


async def test_json_body_sent(make_transport: Any, mocked: aioresponses) -> None:
    mocked.post(f"{BASE}/things/get-things?limit=5&offset=0", status=200, payload=[])
    await make_transport().execute(LIST, params={"limit": 5, "offset": 0}, json={"objects": ["a"]})
    req = calls(mocked, "POST", f"{BASE}/things/get-things")[0]
    assert req.kwargs["json"] == {"objects": ["a"]}
    assert ("limit", "5") in req.kwargs["params"]


# --- вспомогательные функции --------------------------------------------------------------------


def test_encode_query() -> None:
    from datetime import datetime, timezone

    assert encode_query({"a": None, "b": True, "c": [1, None, 2], "d": "x"}) == (
        ("b", "true"), ("c", "1"), ("c", "2"), ("d", "x"),
    )
    assert encode_query({"t": datetime(2025, 6, 14, 19, tzinfo=timezone.utc)}) == (("t", "1749927600000"),)
    assert encode_query(None) == ()


def test_format_path() -> None:
    assert format_path("/spaces/{spaceId}/meters", {"spaceId": "a/b c"}) == "/spaces/a%2Fb%20c/meters"
    with pytest.raises(ValueError, match="spaceId"):
        format_path("/spaces/{spaceId}", {})


def test_prepare_does_not_send(make_transport: Any) -> None:
    req = make_transport().prepare(CREATE, params={"x": 1}, json={"name": "n"})
    assert req.describe() == "POST /things?x=1"
    assert req.kind == "W"
    assert req.json == {"name": "n"}
