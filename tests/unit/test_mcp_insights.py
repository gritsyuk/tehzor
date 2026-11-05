"""Аналитические инструменты MCP на заглушках: объекты, дочерние, сводка, приёмки по нескольким объектам, проекты."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest
from aioresponses import CallbackResult, aioresponses
from mcp.shared.memory import create_connected_server_and_client_session

from tehzor import TehzorClient
from tehzor.mcp import create_server
from tests.conftest import BASE
from tests.unit.test_mcp import data, settings, text

ROOT = "00000000-0000-4000-8000-000000000001"
K1 = "00000000-0000-4000-8000-000000000002"
K2 = "00000000-0000-4000-8000-000000000003"
OLD_ROOT = "aaaaaaaaaaaaaaaaaaaaaaaa"


def mock_objects(m: aioresponses) -> None:
    m.get(f"{BASE}/categories-sets", payload=[{"id": "cs", "objects": [ROOT, K1, K2]}], repeat=True)
    m.get(f"{BASE}/tags-sets", payload=[], repeat=True)
    m.get(f"{BASE}/check-lists", payload=[], repeat=True)
    m.get(f"{BASE}/objects/{ROOT}", payload={"id": ROOT, "name": "ЖК Тест", "externalId": OLD_ROOT}, repeat=True)
    m.get(f"{BASE}/objects/{K1}", payload={"id": K1, "name": "Корпус 1", "parentId": ROOT}, repeat=True)
    m.get(f"{BASE}/objects/{K2}", payload={"id": K2, "name": "Корпус 2", "parentId": ROOT}, repeat=True)


def problems_by_object(per_object: dict[str, list[dict[str, Any]]]) -> Any:
    def callback(url: Any, **kwargs: Any) -> CallbackResult:
        body = kwargs.get("json") or {}
        offset = int(dict(kwargs.get("params") or []).get("offset", 0)) if isinstance(kwargs.get("params"), list) \
            else int(url.query.get("offset", 0))
        items = [p for o in body.get("objects", []) for p in per_object.get(o, [])]
        return CallbackResult(payload=items[offset:])

    return callback


@pytest.fixture
async def session_factory(tmp_path: Path):  # type: ignore[no-untyped-def]
    clients: list[TehzorClient] = []

    def make(**kw: Any) -> Any:
        client = TehzorClient(api_key="k", rate_limit=0, retries=0, read_only=True)
        clients.append(client)
        return create_connected_server_and_client_session(create_server(settings(tmp_path, **kw), client=client))

    yield make
    for c in clients:
        await c.close()


GET_PROBLEMS = re.compile(rf"^{re.escape(BASE)}/problems/get-problems.*$")


async def test_objects_discover_tree_and_new_objects(session_factory: Any, mocked: aioresponses) -> None:
    mock_objects(mocked)
    async with session_factory() as s:
        first = data(await s.call_tool("objects_discover", {}))
    assert first["count"] == 3 and first["roots"] == 1
    root = first["tree"][0]
    assert root["name"] == "ЖК Тест" and [c["name"] for c in root["children"]] == ["Корпус 1", "Корпус 2"]
    assert first["new_since_last"] == []  # первый обход — снимок только создаётся


async def test_problems_summary_includes_children(session_factory: Any, mocked: aioresponses) -> None:
    mock_objects(mocked)
    perf = {"id": "u1", "fullName": "Иванов", "position": "Прораб, ООО «Альфа»"}
    mocked.post(GET_PROBLEMS, callback=problems_by_object({
        ROOT: [{"id": "r1", "status": {"id": "waiting"}, "object": {"id": ROOT}, "plannedFixDate": 1000}],
        K1: [{"id": "k1", "status": {"id": "handling"}, "object": {"id": K1}, "critical": True,
              "performers": [perf]}],
        K2: [],
    }), repeat=True)
    async with session_factory() as s:
        out = data(await s.call_tool("problems_summary", {"objects": [ROOT]}))
    assert out["scope"]["objects"] == 3  # ЖК + 2 корпуса
    assert out["totals"]["open"] == 2 and out["totals"]["overdue"] == 1 and out["totals"]["critical"] == 1
    names = {g["name"] for g in out["groups"]["object"]["items"]}
    assert names == {"ЖК Тест", "ЖК Тест / Корпус 1"}
    assert out["groups"]["contractor"]["items"][0]["key"] in {"альфа", "—"}
    # открытые статусы фильтруются на стороне API
    bodies = [r.kwargs["json"] for (m, u), rs in mocked.requests.items() if m == "POST" for r in rs]
    assert all(b["statuses"] == ["handling", "verification", "waiting", "expired"] for b in bodies)
    assert sorted(b["objects"][0] for b in bodies) == sorted([ROOT, K1, K2])  # по объекту на запрос


async def test_problems_summary_truncation_is_reported(session_factory: Any, mocked: aioresponses) -> None:
    mock_objects(mocked)
    many = [{"id": f"p{i}", "status": {"id": "waiting"}, "object": {"id": K1}} for i in range(120)]
    mocked.post(GET_PROBLEMS, callback=problems_by_object({K1: many}), repeat=True)
    async with session_factory() as s:
        out = data(await s.call_tool("problems_summary", {"objects": [K1], "include_children": False,
                                                          "max_items": 60}))
    assert out["totals"]["open"] == 60
    assert out["truncated_objects"][0]["id"] == K1 and "нижняя граница" in out["note"]


async def test_old_object_id_resolved_to_uuid(session_factory: Any, mocked: aioresponses) -> None:
    mock_objects(mocked)
    mocked.post(GET_PROBLEMS, callback=problems_by_object({ROOT: [{"id": "r1", "status": {"id": "waiting"}}]}),
                repeat=True)
    async with session_factory() as s:
        out = data(await s.call_tool("problems_search", {"objects": [OLD_ROOT]}))
        bad = await s.call_tool("problems_search", {"objects": ["bbbbbbbbbbbbbbbbbbbbbbbb"]})
    assert out["count"] == 1
    sent = [r.kwargs["json"]["objects"] for (m, u), rs in mocked.requests.items() if m == "POST" for r in rs]
    assert sent == [[ROOT]]
    assert bad.isError and "только UUID" in text(bad)


async def test_work_acceptances_search_several_objects_and_statuses(session_factory: Any,
                                                                   mocked: aioresponses) -> None:
    def callback(url: Any, **kwargs: Any) -> CallbackResult:
        obj = url.query.get("objectId")
        status = (kwargs.get("json") or {}).get("status")
        rows = {(K1, "accepted"): [{"id": "w1", "objectId": K1, "createdAt": 2000}],
                (K1, "rejected"): [{"id": "w2", "objectId": K1, "createdAt": 3000}],
                (K2, "accepted"): [{"id": "w3", "objectId": K2, "createdAt": 1000}],
                (K2, "rejected"): [{"id": "w1", "objectId": K1, "createdAt": 2000}]}  # дубль
        return CallbackResult(payload=rows.get((obj, status), []) if int(url.query.get("offset", 0)) == 0 else [])

    mocked.post(re.compile(rf"^{re.escape(BASE)}/work-acceptances/get-work-acceptances.*$"), callback=callback,
                repeat=True)
    async with session_factory() as s:
        out = data(await s.call_tool("work_acceptances_search",
                                     {"objects": [K1, K2], "statuses": ["accepted", "rejected"]}))
    assert [i["id"] for i in out["items"]] == ["w2", "w1", "w3"]  # дедупликация, новые сверху
    assert out["objects"] == 2


async def test_projects_without_config(session_factory: Any, mocked: aioresponses) -> None:
    async with session_factory() as s:
        listed = data(await s.call_tool("projects_list", {}))
        resolved = data(await s.call_tool("project_resolve", {"query": "SIG"}))
        by_project = await s.call_tool("problems_summary", {"project": "SIG"})
    assert listed["configured"] is False and resolved["configured"] is False
    assert by_project.isError and "TEHZOR_MCP_PROJECTS" in text(by_project)
    assert not mocked.requests


async def test_project_code_scope(session_factory: Any, mocked: aioresponses, tmp_path: Path) -> None:
    mock_objects(mocked)
    (tmp_path / "kg").mkdir()
    (tmp_path / "kg" / "test.md").write_text(f"---\ncode: TST\ntitle: ЖК Тест\ntehzor: {ROOT}\n---\nОписание.\n",
                                             encoding="utf-8")
    mocked.post(GET_PROBLEMS, callback=problems_by_object({K2: [{"id": "x", "status": {"id": "waiting"}}]}),
                repeat=True)
    async with session_factory(projects=tmp_path / "kg") as s:
        resolved = data(await s.call_tool("project_resolve", {"query": "tst"}))
        found = data(await s.call_tool("problems_search", {"project": "TST", "include_children": True}))
        tree = data(await s.call_tool("objects_discover", {}))
    match = resolved["matches"][0]
    assert match["code"] == "TST" and [o["id"] for o in match["objects"]] == [ROOT, K1, K2]
    assert found["objects"] == 3 and found["count"] == 1
    assert tree["tree"][0]["project_code"] == "TST"
    assert json.dumps(tree, ensure_ascii=False).count("project_code") == 1  # только размеченный объект
