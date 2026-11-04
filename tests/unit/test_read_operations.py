"""Читающие операции на заглушках: метод, URL, query, тело запроса и разбор ответа."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import pytest
from aioresponses import aioresponses
from yarl import URL

from tehzor import REGISTRY, TehzorClient
from tehzor.models.comments import CommentFilters
from tehzor.models.problems import ProblemFilters
from tehzor.models.spaces import SpaceFilters
from tehzor.models.tasks import TaskFilters
from tehzor.models.work_acceptances import WorkAcceptanceFilters
from tests.conftest import BASE

O = "00000000-0000-4000-8000-000000000001"  # noqa: E741
ITEM = {"id": "x1", "name": "n"}
LIST = [ITEM]

Call = Callable[[TehzorClient], Awaitable[Any]]

# tool: (вызов, HTTP-метод, путь с query, тело запроса или None, ответ)
CASES: dict[str, tuple[Call, str, str, Any, Any]] = {
    "objects_get": (lambda c: c.objects.get(O), "GET", f"/objects/{O}", None, {"id": O}),
    "objects_stages": (lambda c: c.objects.stages(), "GET", "/stages", None, LIST),
    "objects_processes": (lambda c: c.objects.processes(), "GET", "/processes", None, LIST),
    "service_health": (lambda c: c.health(), "GET", "/health/readiness", None, {"status": "ok"}),
    "problems_get": (lambda c: c.problems.get("p1"), "GET", "/problems/p1", None, {"id": "p1"}),
    "problems_list": (lambda c: c.problems.list(ProblemFilters(objects=[O]), limit=5, user_id="u"), "POST",
                      "/problems/get-problems?limit=5&offset=0&userId=u", {"objects": [O]}, LIST),
    "problems_reply": (lambda c: c.problems.reply("p1"), "GET", "/problems/p1/reply", None, {"id": "r"}),
    "problems_statuses": (lambda c: c.problems.statuses(), "GET", "/problem-statuses", None, LIST),
    "spaces_list": (lambda c: c.spaces.list(SpaceFilters(objects=[O], include_objects_children=True)), "POST",
                    "/spaces/get-spaces?limit=50&offset=0", {"objects": [O], "includeObjectsChildren": True}, LIST),
    "spaces_get": (lambda c: c.spaces.get("s1"), "GET", "/spaces/s1", None, {"id": "s1"}),
    "spaces_get_status": (lambda c: c.spaces.get_status("s1"), "GET", "/spaces/s1/status", None, ITEM),
    "spaces_meters": (lambda c: c.spaces.meters("s1"), "GET", "/spaces/s1/meters", None, LIST),
    "spaces_owner_acceptances": (lambda c: c.spaces.owner_acceptances("s1", ["id", "number"]), "GET",
                                 "/spaces/s1/owner-acceptances?fields=id&fields=number", None, LIST),
    "spaces_warranty_claims": (lambda c: c.spaces.warranty_claims("s1"), "GET", "/spaces/s1/warranty-claims",
                               None, LIST),
    "spaces_types": (lambda c: c.spaces.types(), "GET", "/space-types", None, LIST),
    "spaces_meter_types": (lambda c: c.spaces.meter_types(), "GET", "/meter-types", None, LIST),
    "spaces_contract_forms": (lambda c: c.spaces.contract_forms(), "GET", "/contract-forms", None, LIST),
    "spaces_decoration_sets": (lambda c: c.spaces.decoration_sets(), "GET", "/space-types-decorations", None,
                               [{"id": "d", "spaceTypesDecorations": [{"id": "t", "spaceTypes": ["flats"]}]}]),
    "spaces_status_sets": (lambda c: c.spaces.status_sets(), "GET", "/space-statuses", None,
                           [{"id": "set", "spaceStatuses": [{"id": "st", "stage": "transfer"}]}]),
    "work_acceptances_get": (lambda c: c.work_acceptances.get("w1"), "GET", "/work-acceptances/w1", None,
                             {"id": "w1"}),
    "work_acceptances_list": (
        lambda c: c.work_acceptances.list(O, WorkAcceptanceFilters(status="accepted"), limit=10), "POST",
        f"/work-acceptances/get-work-acceptances?limit=10&offset=0&objectId={O}", {"status": "accepted"}, LIST),
    "work_acceptances_statuses": (lambda c: c.work_acceptances.statuses(), "GET", "/work-acceptance-statuses",
                                  None, LIST),
    "work_acceptances_front_types": (lambda c: c.work_acceptances.front_types(), "GET",
                                     "/work-acceptance-front-types", None, LIST),
    "work_acceptances_types": (lambda c: c.work_acceptances.types(), "GET", "/work-acceptance-types", None, LIST),
    "internal_acceptances_list": (lambda c: c.internal_acceptances.list(O, limit=3), "POST",
                                  f"/internal-acceptances/get-internal-acceptances?objectId={O}&limit=3&offset=0",
                                  None, LIST),
    "internal_acceptances_get": (lambda c: c.internal_acceptances.get("i1"), "GET", "/internal-acceptances/i1",
                                 None, {"id": "i1"}),
    "internal_acceptances_problems": (lambda c: c.internal_acceptances.problems("i1"), "GET",
                                      "/internal-acceptances/i1/problems", None, LIST),
    "owner_acceptances_get": (lambda c: c.owner_acceptances.get("oa"), "GET", "/owner-acceptances/oa", None,
                              {"id": "oa", "resolution": {"_id": "accepted", "name": "Принято"}}),
    "owner_acceptances_resolutions": (lambda c: c.owner_acceptances.resolutions(), "GET",
                                      "/owner-acceptance-resolutions", None, LIST),
    "owner_acceptances_statuses": (lambda c: c.owner_acceptances.statuses(), "GET", "/owner-acceptance-statuses",
                                   None, LIST),
    "warranty_claims_get": (lambda c: c.warranty_claims.get("wc"), "GET", "/warranty-claims/wc", None,
                            {"id": "wc", "status": "done"}),
    "warranty_claims_problems": (lambda c: c.warranty_claims.problems("wc", ["id"]), "GET",
                                 "/warranty-claims/wc/problems?fields=id", None, LIST),
    "warranty_claims_statuses": (lambda c: c.warranty_claims.statuses(), "GET", "/warranty-claim-statuses", None,
                                 LIST),
    "tasks_list": (lambda c: c.tasks.list(TaskFilters(objects=[O])), "POST", "/tasks/get-tasks?limit=50&offset=0",
                   {"objects": [O]}, LIST),
    "tasks_get": (lambda c: c.tasks.get("t1"), "GET", "/tasks/t1", None, {"id": "t1"}),
    "tasks_types": (lambda c: c.tasks.types(), "GET", "/task-types", None, LIST),
    "tasks_statuses": (lambda c: c.tasks.statuses(), "GET", "/task-statuses", None, LIST),
    "comments_get": (lambda c: c.comments.get("c1"), "GET", "/comments/c1", None, {"id": "c1", "number": None}),
    "comments_list": (lambda c: c.comments.list(CommentFilters(problem_id="p1", official=True)), "POST",
                      "/comments/get-comments?limit=50&offset=0", {"problemId": "p1", "official": True}, LIST),
    "categories_list": (lambda c: c.categories.list("set"), "GET", "/categories?setId=set", None, LIST),
    "categories_sets": (lambda c: c.categories.sets(O), "GET", f"/categories-sets?objectId={O}", None, LIST),
    "tags_list": (lambda c: c.tags.list("set"), "GET", "/tags?setId=set", None, LIST),
    "tags_sets": (lambda c: c.tags.sets(), "GET", "/tags-sets", None, LIST),
    "check_lists_list": (lambda c: c.check_lists.list(O, "acceptance"), "GET",
                         f"/check-lists?objectId={O}&stage=acceptance", None, LIST),
    "check_lists_get": (lambda c: c.check_lists.get("cl"), "GET", "/check-lists/cl", None,
                        {"id": "cl", "checkItems": [{"id": "ci"}]}),
    "check_lists_get_status": (lambda c: c.check_lists.get_status("cl", "s1"), "GET",
                               "/check-lists/status?checkListId=cl&spaceId=s1", None, {"statusName": "В работе"}),
    "check_lists_get_item_status": (lambda c: c.check_lists.get_item_status("ci", "s1"), "GET",
                                    "/check-lists/item-status?checkItemId=ci&spaceId=s1", None, {"id": "ci"}),
    "check_lists_item_statuses": (lambda c: c.check_lists.item_statuses(), "GET", "/check-item-statuses", None,
                                  LIST),
    "check_lists_statuses": (lambda c: c.check_lists.statuses(), "GET", "/check-list-statuses", None, LIST),
    "checks_get": (lambda c: c.checks.get("ch"), "GET", "/checks/ch", None, {"id": "ch", "links": {}}),
}


def _norm(url: str) -> URL:
    u = URL(url)
    return u.with_query(sorted(u.query.items()))


def test_every_read_operation_has_unit_case() -> None:
    assert sorted(op.tool_name for op in REGISTRY.all() if op.kind == "R") == sorted(CASES)


@pytest.fixture
async def client():  # type: ignore[no-untyped-def]
    async with TehzorClient(api_key="k", rate_limit=0) as thz:
        yield thz


@pytest.mark.parametrize("tool", sorted(CASES))
async def test_read_operation(tool: str, client: TehzorClient, mocked: aioresponses) -> None:
    call, method, path, body, payload = CASES[tool]
    url = f"{BASE}{path}"
    mocked.add(url, method=method, payload=payload)
    result = await call(client)
    assert result is not None

    reqs = [r for (m, u), rs in mocked.requests.items() if m == method for r in rs
            if _norm(str(u)) == _norm(url)]
    assert len(reqs) == 1, f"ожидался {method} {url}, были: {list(mocked.requests)}"
    assert reqs[0].kwargs.get("json") == body
    op = REGISTRY.by_tool(tool)
    assert op.method == method


async def test_meters_404_means_empty(client: TehzorClient, mocked: aioresponses) -> None:
    mocked.get(f"{BASE}/spaces/s1/meters", status=404, payload={"message": "Не удалось найти приборы учета"})
    assert await client.spaces.meters("s1") == []


async def test_reply_404_means_none(client: TehzorClient, mocked: aioresponses) -> None:
    mocked.get(f"{BASE}/problems/p1/reply", status=404, payload={"message": "Ответ не найден"})
    assert await client.problems.reply("p1") is None


async def test_decoration_sets_accepts_single_object(client: TehzorClient, mocked: aioresponses) -> None:
    mocked.get(f"{BASE}/space-types-decorations", payload={"id": "d", "name": "Набор"})
    assert [s.id for s in await client.spaces.decoration_sets()] == ["d"]


async def test_list_without_object_filter_warns(client: TehzorClient, mocked: aioresponses) -> None:
    mocked.post(f"{BASE}/problems/get-problems?limit=50&offset=0", payload=[])
    with pytest.warns(UserWarning, match="без фильтра по объекту"):
        await client.problems.list()


async def test_iter_paginates(client: TehzorClient, mocked: aioresponses) -> None:
    mocked.post(f"{BASE}/tasks/get-tasks?limit=2&offset=0", payload=[{"id": "1"}, {"id": "2"}])
    mocked.post(f"{BASE}/tasks/get-tasks?limit=2&offset=2", payload=[{"id": "3"}])
    ids = [t.id async for t in client.tasks.iter(TaskFilters(objects=[O]), page_size=2)]
    assert ids == ["1", "2", "3"]
