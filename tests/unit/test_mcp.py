"""MCP-сервер: инструменты из реестра, чтение, ошибки, контроль записи. Только заглушки (aioresponses)."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest
from aioresponses import aioresponses
from mcp import types
from mcp.shared.memory import create_connected_server_and_client_session

from tehzor import REGISTRY, TehzorClient
from tehzor.mcp import Settings, create_server
from tehzor.mcp.__main__ import BearerAuth
from tests.conftest import BASE

O = "00000000-0000-4000-8000-000000000001"  # noqa: E741


def text(result: types.CallToolResult) -> str:
    return "".join(c.text for c in result.content if isinstance(c, types.TextContent))


def data(result: types.CallToolResult) -> Any:
    assert not result.isError, text(result)
    return json.loads(text(result))


def settings(tmp_path: Path, **kw: Any) -> Settings:
    kw.setdefault("state_dir", tmp_path / "state")
    return Settings(audit_log=tmp_path / "audit.jsonl", **kw)


def audit(tmp_path: Path) -> list[dict[str, Any]]:
    path = tmp_path / "audit.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()] if path.exists() else []


@pytest.fixture
async def make_session(tmp_path: Path):  # type: ignore[no-untyped-def]
    clients: list[TehzorClient] = []

    async def _make(elicitation_callback: Any = None, **kw: Any) -> AsyncIterator[Any]:
        s = settings(tmp_path, **kw)
        client = TehzorClient(api_key="k", rate_limit=0, retries=0, read_only=not s.allow_write)
        clients.append(client)
        srv = create_server(s, client=client)
        return create_connected_server_and_client_session(srv, elicitation_callback=elicitation_callback)

    yield _make
    for c in clients:
        await c.close()


# --- инструменты и ресурсы -----------------------------------------------------------------------


async def test_tools_cover_registry(make_session: Any, mocked: aioresponses) -> None:
    async with await make_session() as session:
        tools = {t.name: t for t in (await session.list_tools()).tools}
    expected = {op.tool_name for op in REGISTRY.all() if op.mcp}
    assert len(expected) == 73
    extra = {"confirm_operation", "problems_search", "space_overview", "objects_discover", "problems_summary",
             "work_acceptances_search", "projects_list", "project_resolve"}
    assert set(tools) == expected | extra
    for op in REGISTRY.all():
        if not op.mcp:
            continue
        ann = tools[op.tool_name].annotations
        assert ann is not None
        assert ann.readOnlyHint is (op.kind == "R"), op.tool_name
        assert ann.destructiveHint is (op.kind != "R"), op.tool_name
        if op.kind != "R":
            assert "ИЗМЕНЯЕТ ДАННЫЕ" in (tools[op.tool_name].description or "")
    assert "service_health" not in tools  # недокументированный служебный метод не публикуется
    assert tools["confirm_operation"].annotations.destructiveHint  # type: ignore[union-attr]


async def test_tool_schema_from_library_models(make_session: Any, mocked: aioresponses) -> None:
    async with await make_session() as session:
        tools = {t.name: t for t in (await session.list_tools()).tools}
    schema = tools["problems_create"].inputSchema
    assert schema["required"] == ["data"]
    props = schema["$defs"]["ProblemCreate"]["properties"]
    assert {"objectId", "stage", "processId"} <= set(props)  # схема в camelCase, как в API; принимаются оба написания
    assert "dry_run" not in schema["properties"]  # dry_run — внутренний механизм превью
    assert "ctx" not in schema["properties"]


async def test_hide_write_tools(make_session: Any, mocked: aioresponses) -> None:
    async with await make_session(hide_write_tools=True) as session:
        names = {t.name for t in (await session.list_tools()).tools}
    assert "problems_create" not in names and "confirm_operation" not in names
    assert "problems_get" in names


async def test_dictionary_resource_cached(make_session: Any, mocked: aioresponses) -> None:
    mocked.get(f"{BASE}/problem-statuses", payload=[{"id": "waiting", "name": "К устранению"}])
    async with await make_session() as session:
        uris = {str(r.uri) for r in (await session.list_resources()).resources}
        assert "tehzor://problem-statuses" in uris and "tehzor://objects-tree" in uris and len(uris) == 19
        for _ in range(2):
            res = await session.read_resource("tehzor://problem-statuses")  # type: ignore[arg-type]
            assert json.loads(res.contents[0].text) == [{"id": "waiting", "name": "К устранению"}]  # type: ignore[union-attr]
    assert sum(len(v) for v in mocked.requests.values()) == 1  # второй раз — из кеша


# --- чтение ----------------------------------------------------------------------------------------


async def test_read_tool_returns_compact_json_with_iso_dates(make_session: Any, mocked: aioresponses) -> None:
    mocked.get(f"{BASE}/problems/p1", payload={"id": "p1", "number": 5, "createdAt": 1749927600000, "floor": None})
    async with await make_session() as session:
        result = data(await session.call_tool("problems_get", {"problem_id": "p1"}))
    assert result == {"id": "p1", "number": 5, "created_at": "2025-06-14T19:00:00+00:00"}


async def test_list_requires_object_filter(make_session: Any, mocked: aioresponses) -> None:
    async with await make_session() as session:
        result = await session.call_tool("problems_list", {})
    assert result.isError and "filters.objects" in text(result)
    assert not mocked.requests


async def test_list_pagination_envelope(make_session: Any, mocked: aioresponses) -> None:
    mocked.post(f"{BASE}/problems/get-problems?limit=2&offset=4", payload=[{"id": "a"}, {"id": "b"}])
    async with await make_session() as session:
        result = data(await session.call_tool("problems_list", {"filters": {"objects": [O]}, "limit": 2, "offset": 4}))
    assert result == {"items": [{"id": "a"}, {"id": "b"}], "count": 2, "offset": 4, "next_offset": 6}


async def test_list_limit_capped(make_session: Any, mocked: aioresponses) -> None:
    async with await make_session() as session:
        result = await session.call_tool("tasks_list", {"filters": {"objects": [O]}, "limit": 5000})
    assert result.isError and "limit" in text(result)


async def test_api_error_is_readable(make_session: Any, mocked: aioresponses) -> None:
    mocked.get(f"{BASE}/problems/x", status=404, payload={"message": "Нарушение не найдено"})
    async with await make_session() as session:
        result = await session.call_tool("problems_get", {"problem_id": "x"})
    assert result.isError and "Не найдено (404): Нарушение не найдено" in text(result)


async def test_problems_search_compact(make_session: Any, mocked: aioresponses) -> None:
    mocked.post(
        f"{BASE}/problems/get-problems?limit=3&offset=0",
        payload=[
            {"id": "p1", "number": 1, "status": {"id": "waiting", "name": "К устранению"}, "description": "x" * 500},
        ],
    )
    async with await make_session() as session:
        result = data(await session.call_tool("problems_search", {"objects": [O], "limit": 3}))
    item = result["items"][0]
    assert item["status"] == "К устранению" and len(item["description"]) == 200
    assert result["count"] == 1 and result["truncated"] is False


async def test_space_overview(make_session: Any, mocked: aioresponses) -> None:
    mocked.get(f"{BASE}/spaces/s1", payload={"id": "s1", "name": "300"})
    mocked.get(f"{BASE}/spaces/s1/status", payload={"id": "st", "name": "Не осмотрено"})
    mocked.get(f"{BASE}/spaces/s1/meters", status=404, payload={})
    mocked.get(f"{BASE}/spaces/s1/owner-acceptances", payload=[])
    mocked.get(f"{BASE}/spaces/s1/warranty-claims", payload=[])
    async with await make_session() as session:
        result = data(await session.call_tool("space_overview", {"space_id": "s1"}))
    assert result["space"]["name"] == "300" and result["meters"] == []


# --- запись: контроль человека ---------------------------------------------------------------------

CREATE_ARGS = {
    "data": {"object_id": O, "stage": "building", "process_id": "operational-control", "description": "Скол"}
}
CREATE_BODY = {"objectId": O, "stage": "building", "processId": "operational-control", "description": "Скол"}


def sent(mocked: aioresponses) -> list[Any]:
    return [r for (m, _), rs in mocked.requests.items() if m != "GET" for r in rs]


async def test_write_disabled_by_default(make_session: Any, mocked: aioresponses, tmp_path: Path) -> None:
    async with await make_session() as session:
        result = await session.call_tool("problems_create", CREATE_ARGS)
        confirm = await session.call_tool("confirm_operation", {"confirmation_id": "x"})
    assert result.isError and "запись отключена" in text(result)
    assert confirm.isError
    assert not mocked.requests


async def test_write_two_step_confirmation(make_session: Any, mocked: aioresponses, tmp_path: Path) -> None:
    mocked.post(f"{BASE}/problems", payload={"id": "p9", "number": 9})
    async with await make_session(allow_write=True) as session:
        preview = data(await session.call_tool("problems_create", CREATE_ARGS))
        assert preview["status"] == "pending_confirmation"
        assert preview["preview"]["request"] == {
            "method": "POST",
            "path": "/problems",
            "query": None,
            "body": CREATE_BODY,
        }
        assert not sent(mocked)  # без подтверждения ничего не отправлено

        done = data(await session.call_tool("confirm_operation", {"confirmation_id": preview["confirmation_id"]}))
        assert done["status"] == "done" and done["result"]["id"] == "p9"
        reqs = sent(mocked)
        assert len(reqs) == 1 and reqs[0].kwargs["json"] == CREATE_BODY  # отправлено ровно показанное

        again = await session.call_tool("confirm_operation", {"confirmation_id": preview["confirmation_id"]})
        assert again.isError and "не найден или истёк" in text(again)  # одноразовый
    events = [e["event"] for e in audit(tmp_path)]
    assert events == ["preview", "confirmed", "executed", "confirm_rejected"]


async def test_confirmation_expires(make_session: Any, mocked: aioresponses) -> None:
    async with await make_session(allow_write=True, confirm_ttl=0) as session:
        preview = data(await session.call_tool("problems_create", CREATE_ARGS))
        result = await session.call_tool("confirm_operation", {"confirmation_id": preview["confirmation_id"]})
    assert result.isError and not sent(mocked)


async def test_unknown_confirmation_id(make_session: Any, mocked: aioresponses) -> None:
    async with await make_session(allow_write=True) as session:
        result = await session.call_tool("confirm_operation", {"confirmation_id": "forged"})
    assert result.isError and not sent(mocked)


async def test_write_allowlist(make_session: Any, mocked: aioresponses) -> None:
    async with await make_session(allow_write=True, write_tools=frozenset({"comments_create"})) as session:
        result = await session.call_tool("problems_create", CREATE_ARGS)
    assert result.isError and "TEHZOR_MCP_WRITE_TOOLS" in text(result) and not mocked.requests


async def test_write_invalid_args_rejected_before_network(make_session: Any, mocked: aioresponses) -> None:
    bad = {"data": {**CREATE_ARGS["data"], "stage": "moon"}}
    async with await make_session(allow_write=True) as session:
        result = await session.call_tool("problems_create", bad)
    assert result.isError and not mocked.requests


async def test_audit_masks_personal_data(make_session: Any, mocked: aioresponses, tmp_path: Path) -> None:
    async with await make_session(allow_write=True) as session:
        await session.call_tool("space_owners_create", {"data": {"name": "Иванов Иван", "phone": "+7900"}})
    raw = (tmp_path / "audit.jsonl").read_text(encoding="utf-8")
    assert "Иванов" not in raw and "+7900" not in raw and "***" in raw


async def _accept(context: Any, params: types.ElicitRequestParams) -> types.ElicitResult:
    assert "POST /problems" in params.message
    return types.ElicitResult(action="accept", content={"confirm": True})


async def _decline(context: Any, params: types.ElicitRequestParams) -> types.ElicitResult:
    return types.ElicitResult(action="decline")


async def test_elicitation_accept_executes(make_session: Any, mocked: aioresponses, tmp_path: Path) -> None:
    mocked.post(f"{BASE}/problems", payload={"id": "p9"})
    async with await make_session(allow_write=True, elicitation_callback=_accept) as session:
        result = data(await session.call_tool("problems_create", CREATE_ARGS))
    assert result["status"] == "done" and len(sent(mocked)) == 1
    assert [e["event"] for e in audit(tmp_path)] == ["preview", "confirmed", "executed"]


async def test_elicitation_decline_sends_nothing(make_session: Any, mocked: aioresponses, tmp_path: Path) -> None:
    async with await make_session(allow_write=True, elicitation_callback=_decline) as session:
        result = data(await session.call_tool("problems_create", CREATE_ARGS))
    assert result["status"] == "declined" and not sent(mocked)
    assert [e["event"] for e in audit(tmp_path)] == ["preview", "declined"]


async def test_create_not_retried_after_confirmation(make_session: Any, mocked: aioresponses) -> None:
    mocked.post(f"{BASE}/problems", status=503)
    mocked.post(f"{BASE}/problems", payload={"id": "dup"})
    async with await make_session(allow_write=True, elicitation_callback=_accept) as session:
        result = await session.call_tool("problems_create", CREATE_ARGS)
    assert result.isError and len(sent(mocked)) == 1


# --- HTTP-авторизация --------------------------------------------------------------------------------


async def test_bearer_auth() -> None:
    calls: list[Any] = []

    async def app(scope: Any, receive: Any, send: Any) -> None:
        calls.append(scope["type"])

    guard = BearerAuth(app, "secret")
    out: list[dict[str, Any]] = []

    async def send(msg: dict[str, Any]) -> None:
        out.append(msg)

    await guard({"type": "http", "headers": [(b"authorization", b"Bearer wrong")]}, None, send)
    assert out[0]["status"] == 401 and not calls
    await guard({"type": "http", "headers": [(b"authorization", b"Bearer secret")]}, None, send)
    await guard({"type": "lifespan"}, None, send)
    assert calls == ["http", "lifespan"]
