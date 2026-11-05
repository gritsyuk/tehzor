"""Контракт аналитики на живом API (только чтение): обход объектов, даты фильтра, статус expired."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from tehzor import TehzorClient
from tehzor.insights import discover_objects, summarize_problems
from tehzor.insights.summary import FETCH_STATUSES
from tehzor.models.problems import ProblemFilters

from .conftest import Ids

pytestmark = pytest.mark.contract


async def test_discover_objects_builds_full_tree(live: TehzorClient, ids: Ids) -> None:
    tree = await discover_objects(live)
    assert len(tree) > 0 and tree.roots()
    orphans = [i for i in tree.nodes if tree.nodes[i].parent_id and tree.parent_of(i) not in tree.nodes]
    assert not orphans, f"родитель не найден: {orphans[:5]}"
    for oid in ids.objects:
        assert tree.resolve(oid), f"seed-объект {oid} не найден обходом"


async def test_modified_at_filter_is_applied(live: TehzorClient, ids: Ids) -> None:
    """fact: строку мс сервер игнорирует — клиент шлёт ISO; дата в будущем → 0, в прошлом → не 0."""
    obj = ids.objects[0]
    future = datetime.now(timezone.utc) + timedelta(days=3650)
    assert await live.problems.list(ProblemFilters(objects=[obj], modified_at_from=future), limit=5) == []
    past = datetime(2000, 1, 1, tzinfo=timezone.utc)
    if not await live.problems.list(ProblemFilters(objects=[obj]), limit=1):
        pytest.skip("у объекта нет нарушений")
    assert await live.problems.list(ProblemFilters(objects=[obj], modified_at_from=past), limit=5)


async def test_expired_status_still_unused(live: TehzorClient, ids: Ids) -> None:
    """fact (2026-11-05): сервер не ставит статус expired — просрочка считается по сроку. Сигнал, если начнёт."""
    statuses = {s.id for s in await live.problems.statuses()}
    found = await live.problems.list(ProblemFilters(objects=ids.objects, statuses=["expired"]), limit=5)
    if "expired" in statuses or found:
        pytest.fail("сервер начал использовать статус expired — пересмотрите is_overdue и docs/API_FACTS.md")


async def test_summary_on_real_object(live: TehzorClient, ids: Ids) -> None:
    filters = ProblemFilters(objects=[ids.objects[0]], statuses=list(FETCH_STATUSES))
    problems = [p async for p in live.problems.iter(filters, max_items=200)]
    out = summarize_problems(problems, now=datetime.now(timezone.utc))
    assert out["totals"]["open"] == len(problems)
    assert out["totals"]["overdue"] <= out["totals"]["open"]
