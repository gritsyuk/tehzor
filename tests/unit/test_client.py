from __future__ import annotations

import pytest
from aioresponses import aioresponses

from tehzor import NotFoundError, TehzorClient
from tehzor.models import ConstructionObject, StageInfo
from tests.conftest import BASE, calls

OBJ_ID = "00000000-0000-4000-8000-000000000001"


@pytest.fixture
async def client():  # type: ignore[no-untyped-def]
    async with TehzorClient(api_key="k", rate_limit=0) as thz:
        yield thz


async def test_objects_get(client: TehzorClient, mocked: aioresponses) -> None:
    mocked.get(f"{BASE}/objects/{OBJ_ID}", payload={
        "id": OBJ_ID, "externalId": "64480db0944e713c0cd68d6d", "name": "Дом 1", "customFields": None,
    })
    obj = await client.objects.get(OBJ_ID)
    assert isinstance(obj, ConstructionObject)
    assert obj.external_id == "64480db0944e713c0cd68d6d"


async def test_objects_stages(client: TehzorClient, mocked: aioresponses) -> None:
    mocked.get(f"{BASE}/stages", payload=[{"id": "building", "name": "Строительство"}])
    assert await client.objects.stages() == [StageInfo(id="building", name="Строительство")]


async def test_objects_processes_empty_body(client: TehzorClient, mocked: aioresponses) -> None:
    mocked.get(f"{BASE}/processes", body=b"")
    assert await client.objects.processes() == []


async def test_not_found(client: TehzorClient, mocked: aioresponses) -> None:
    mocked.get(f"{BASE}/objects/x", status=404, payload={"message": "Объект не найден"})
    with pytest.raises(NotFoundError, match="Объект не найден"):
        await client.objects.get("x")


async def test_health(client: TehzorClient, mocked: aioresponses) -> None:
    mocked.get(f"{BASE}/health/readiness", payload={"status": "ok", "info": {}})
    assert (await client.health()).status == "ok"


async def test_api_key_from_env(monkeypatch: pytest.MonkeyPatch, mocked: aioresponses) -> None:
    monkeypatch.setenv("TEHZOR_API_KEY", "from-env")
    mocked.get(f"{BASE}/stages", payload=[])
    async with TehzorClient(rate_limit=0) as thz:
        await thz.objects.stages()
        assert thz.transport._get_session().headers["api-key"] == "from-env"


async def test_context_manager_closes(mocked: aioresponses) -> None:
    mocked.get(f"{BASE}/stages", payload=[])
    async with TehzorClient(api_key="k", rate_limit=0) as thz:
        await thz.objects.stages()
    assert thz.transport.closed
    assert len(calls(mocked, "GET", f"{BASE}/stages")) == 1
