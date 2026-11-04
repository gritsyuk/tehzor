"""Контракт по каждой читающей операции: модель разбирает фактический ответ без неописанных полей."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import pytest

from tehzor import REGISTRY, ReadOnlyError, TehzorClient
from tehzor._registry import Operation
from tehzor.models import iter_extras
from tehzor.models.comments import CommentFilters
from tehzor.models.problems import ProblemFilters
from tehzor.models.spaces import SpaceFilters
from tehzor.models.tasks import TaskFilters

from .conftest import KNOWN_EXTRAS, SAMPLE, ContractTransport, Ids, Report

pytestmark = pytest.mark.contract

Recipe = Callable[[TehzorClient, Ids], Awaitable[Any]]


async def _first_non_empty(fn: Callable[[str], Awaitable[Any]], candidates: list[str], what: str) -> Any:
    for cid in candidates:
        result = await fn(cid)
        if result:
            return result
    pytest.skip(f"нет данных: {what} (проверено {len(candidates)})")


RECIPES: dict[str, Recipe] = {
    # объекты и служебное
    "objects_get": lambda c, i: c.objects.get(i.objects[0]),
    "objects_stages": lambda c, i: c.objects.stages(),
    "objects_processes": lambda c, i: c.objects.processes(),
    "service_health": lambda c, i: c.health(),
    # нарушения
    "problems_list": lambda c, i: _first_non_empty(
        lambda o: c.problems.list(ProblemFilters(objects=[o]), limit=SAMPLE), i.objects, "нарушения"),
    "problems_get": lambda c, i: c.problems.get(i.need("problems")[0]),
    "problems_reply": lambda c, i: _first_non_empty(c.problems.reply, i.need("problems", 8), "официальный ответ"),
    "problems_statuses": lambda c, i: c.problems.statuses(),
    # помещения
    "spaces_list": lambda c, i: _first_non_empty(
        lambda o: c.spaces.list(SpaceFilters(objects=[o]), limit=SAMPLE), i.objects, "помещения"),
    "spaces_get": lambda c, i: c.spaces.get(i.need("spaces")[0]),
    "spaces_get_status": lambda c, i: c.spaces.get_status(i.need("spaces")[0]),
    "spaces_meters": lambda c, i: _first_non_empty(c.spaces.meters, i.need("spaces", 6), "приборы учёта"),
    "spaces_owner_acceptances": lambda c, i: _first_non_empty(c.spaces.owner_acceptances, i.need("spaces", 6),
                                                              "передачи по помещению"),
    "spaces_warranty_claims": lambda c, i: _first_non_empty(c.spaces.warranty_claims, i.need("spaces", 6),
                                                            "гарантийные обращения по помещению"),
    "spaces_types": lambda c, i: c.spaces.types(),
    "spaces_meter_types": lambda c, i: c.spaces.meter_types(),
    "spaces_contract_forms": lambda c, i: c.spaces.contract_forms(),
    "spaces_decoration_sets": lambda c, i: c.spaces.decoration_sets(),
    "spaces_status_sets": lambda c, i: c.spaces.status_sets(),
    # приёмки работ
    "work_acceptances_list": lambda c, i: _first_non_empty(
        lambda o: c.work_acceptances.list(o, limit=SAMPLE), i.objects, "приёмки работ"),
    "work_acceptances_get": lambda c, i: c.work_acceptances.get(i.need("work_acceptances")[0]),
    "work_acceptances_statuses": lambda c, i: c.work_acceptances.statuses(),
    "work_acceptances_front_types": lambda c, i: c.work_acceptances.front_types(),
    "work_acceptances_types": lambda c, i: c.work_acceptances.types(),
    # внутренние приёмки
    "internal_acceptances_list": lambda c, i: _first_non_empty(
        lambda o: c.internal_acceptances.list(o, limit=SAMPLE), i.objects, "внутренние приёмки"),
    "internal_acceptances_get": lambda c, i: c.internal_acceptances.get(i.need("internal_acceptances")[0]),
    "internal_acceptances_problems": lambda c, i: _first_non_empty(
        c.internal_acceptances.problems, i.need("internal_acceptances", 4), "нарушения внутренней приёмки"),
    # передачи собственникам
    "owner_acceptances_get": lambda c, i: c.owner_acceptances.get(i.need("owner_acceptances")[0]),
    "owner_acceptances_resolutions": lambda c, i: c.owner_acceptances.resolutions(),
    "owner_acceptances_statuses": lambda c, i: c.owner_acceptances.statuses(),
    # гарантия
    "warranty_claims_get": lambda c, i: c.warranty_claims.get(i.need("warranty_claims")[0]),
    "warranty_claims_problems": lambda c, i: _first_non_empty(
        c.warranty_claims.problems, i.need("warranty_claims", 4), "нарушения гарантийного обращения"),
    "warranty_claims_statuses": lambda c, i: c.warranty_claims.statuses(),
    # задачи
    "tasks_list": lambda c, i: _first_non_empty(
        lambda o: c.tasks.list(TaskFilters(objects=[o]), limit=SAMPLE), i.objects, "задачи"),
    "tasks_get": lambda c, i: c.tasks.get(i.need("tasks")[0]),
    "tasks_types": lambda c, i: c.tasks.types(),
    "tasks_statuses": lambda c, i: c.tasks.statuses(),
    # комментарии
    "comments_list": lambda c, i: _first_non_empty(
        lambda pid: c.comments.list(CommentFilters(problem_id=pid), limit=SAMPLE), i.need("problems", 5),
        "комментарии к нарушениям"),
    "comments_get": lambda c, i: c.comments.get(i.need("comments")[0]),
    # виды работ, метки
    "categories_sets": lambda c, i: c.categories.sets(i.objects[0]),
    "categories_list": lambda c, i: c.categories.list(i.need("category_sets")[0]),
    "tags_sets": lambda c, i: c.tags.sets(i.objects[0]),
    "tags_list": lambda c, i: _first_non_empty(c.tags.list, i.need("tag_sets", 5), "метки"),
    # чек-листы и проверки
    "check_lists_list": lambda c, i: _first_non_empty(c.check_lists.list, i.objects, "чек-листы"),
    "check_lists_get": lambda c, i: c.check_lists.get(i.need("check_lists")[0]),
    "check_lists_get_status": lambda c, i: c.check_lists.get_status(i.need("check_lists")[0], i.need("spaces")[0]),
    "check_lists_get_item_status": lambda c, i: c.check_lists.get_item_status(i.need("check_items")[0],
                                                                              i.need("spaces")[0]),
    "check_lists_item_statuses": lambda c, i: c.check_lists.item_statuses(),
    "check_lists_statuses": lambda c, i: c.check_lists.statuses(),
    "checks_get": lambda c, i: c.checks.get(i.need("checks")[0]),
}

READ_OPS = [op for op in REGISTRY.all() if op.kind == "R"]


def test_every_read_operation_has_contract() -> None:
    """Новая читающая операция без контрактного теста — ошибка."""
    assert sorted(op.tool_name for op in READ_OPS) == sorted(RECIPES)


def test_contract_suite_is_read_only() -> None:
    for name in RECIPES:
        assert REGISTRY.by_tool(name).kind == "R", name


async def test_guard_blocks_mutations(live: TehzorClient) -> None:
    write = Operation("Guard_create", "POST", "/problems", "W", idempotent=False, resource="g", name="create")
    with pytest.raises(ReadOnlyError):
        await live.transport.execute(write, json={})
    assert not live.transport.records  # type: ignore[attr-defined]


@pytest.mark.parametrize("tool", sorted(RECIPES))
async def test_operation(tool: str, live: TehzorClient, ids: Ids, report: Report) -> None:
    op = REGISTRY.by_tool(tool)
    try:
        result = await RECIPES[tool](live, ids)
    except pytest.skip.Exception as exc:
        report.skip(op, str(exc))
        raise
    items = result if isinstance(result, list) else [result]
    if not items or items == [None]:
        report.skip(op, "пустой ответ")
        pytest.skip("пустой ответ")
    allowed = set(KNOWN_EXTRAS.get(tool, []))
    extras = sorted({path for item in items for path, _ in iter_extras(item)} - allowed)
    assert isinstance(live.transport, ContractTransport)
    report.record(op, live.transport, len(items), extras)
    assert not extras, f"{tool}: поля ответа не описаны в модели: {extras}"
