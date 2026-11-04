"""Контракт: objects + health. Модель должна разобрать фактический ответ без неописанных полей."""

from __future__ import annotations

import pytest

from tehzor import REGISTRY, ReadOnlyError, TehzorClient
from tehzor._registry import Operation
from tehzor.models import iter_extras

from .conftest import seed

pytestmark = pytest.mark.contract


def test_contract_suite_is_read_only() -> None:
    """В живое API ходят только операции kind == "R"."""
    used = ["objects_get", "objects_stages", "objects_processes", "service_health"]
    assert all(REGISTRY.by_tool(name).kind == "R" for name in used)


async def test_read_only_guard(live: TehzorClient) -> None:
    write = Operation("Guard", "POST", "/problems", "W", idempotent=False, resource="problems", name="create")
    with pytest.raises(ReadOnlyError):
        await live.transport.execute(write, json={})


async def test_stages(live: TehzorClient) -> None:
    stages = await live.objects.stages()
    assert {s.id for s in stages} >= {"building", "acceptance", "transfer", "warranty"}
    assert not [x for s in stages for x in iter_extras(s)]


async def test_processes(live: TehzorClient) -> None:
    processes = await live.objects.processes()
    assert processes
    assert not [x for p in processes for x in iter_extras(p)]


async def test_object(live: TehzorClient) -> None:
    obj = await live.objects.get(seed("OBJECT_ID"))
    assert obj.id
    assert not list(iter_extras(obj))


async def test_health(live: TehzorClient) -> None:
    assert (await live.health()).status == "ok"
