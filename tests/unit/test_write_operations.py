"""Изменяющие операции (24) — ТОЛЬКО на заглушках, на живом API они не вызываются никогда.

Проверяется: метод, URL, query, JSON-тело (camelCase, без None), разбор ответа, dry_run без сети,
read_only блокирует до сети, неидемпотентные операции не повторяются при сбое.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Any

import pytest
from aioresponses import aioresponses
from pydantic import ValidationError
from yarl import URL

from tehzor import REGISTRY, PreparedRequest, ReadOnlyError, ServerError, TehzorClient
from tehzor.enums import (
    CheckRecordStatus,
    CommentType,
    FrontType,
    OwnerAcceptanceResolution,
    OwnerAcceptanceStatus,
    ProblemStatus,
    ProcessId,
    Stage,
    TaskPriority,
    TaskType,
    WorkAcceptanceType,
)
from tehzor.models.acceptances import InternalAcceptanceCreate, OwnerAcceptanceCreate
from tehzor.models.catalog import CategoryCreate, CheckCreate
from tehzor.models.comments import CommentCreate, CommentLinksInput
from tehzor.models.problems import ProblemCreate, ProblemEdit, ProblemLinksInput, ReasonInput
from tehzor.models.space_owners import SpaceOwnerCreate, SpaceOwnerEdit, SpaceOwnerGetOrCreate
from tehzor.models.spaces import SpaceEdit
from tehzor.models.tasks import TaskCreate, TaskEdit
from tehzor.models.warranty_claims import WarrantyClaimCreate
from tehzor.models.work_acceptances import WorkAcceptanceCreate, WorkAcceptanceEdit
from tests.conftest import BASE

O = "00000000-0000-4000-8000-000000000001"  # noqa: E741
T = datetime(2025, 6, 14, 19, tzinfo=timezone.utc)
MS = 1749927600000

Call = Callable[[TehzorClient, bool], Awaitable[Any]]

# tool: (вызов(client, dry_run), HTTP-метод, путь с query, ожидаемое JSON-тело, ответ, проверка результата)
CASES: dict[str, tuple[Call, str, str, Any, Any, Callable[[Any], bool]]] = {
    "spaces_edit": (
        lambda c, d: c.spaces.edit("s1", SpaceEdit(area_bti=55.1, type_decoration="dec", planned_area=56.0,
                                                   decoration_warranty_expired_date=T), dry_run=d),
        "POST", "/spaces/s1",
        {"areaBTI": 55.1, "typeDecoration": "dec", "plannedArea": 56.0, "decorationWarrantyExpiredDate": MS},
        {"id": "s1", "areaBTI": 55.1}, lambda r: r.area_bti == 55.1),
    "spaces_set_status": (
        lambda c, d: c.spaces.set_status("s1", "st1", dry_run=d), "POST", "/spaces/s1/set-status/st1", None,
        {"id": "s1"}, lambda r: r.id == "s1"),
    "space_owners_create": (
        lambda c, d: c.space_owners.create(SpaceOwnerCreate(name="Иванов", spaces=["s1"]), dry_run=d),
        "POST", "/space-owners", {"name": "Иванов", "spaces": ["s1"]}, {"name": "Иванов"},
        lambda r: r.name == "Иванов"),
    "space_owners_get_or_create": (
        lambda c, d: c.space_owners.get_or_create(SpaceOwnerGetOrCreate(name="Иванов", phone="1"), dry_run=d),
        "POST", "/space-owners/get-or-create", {"name": "Иванов", "phone": "1"}, {"id": "ow"},
        lambda r: r.id == "ow"),
    "space_owners_edit": (
        lambda c, d: c.space_owners.edit("ow", SpaceOwnerEdit(comment="к"), dry_run=d), "POST",
        "/space-owners/ow", {"comment": "к"}, {"id": "ow"}, lambda r: r.id == "ow"),
    "space_owners_delete": (
        lambda c, d: c.space_owners.delete("ow", dry_run=d), "DELETE", "/space-owners/ow/delete", None,
        {"deleted": True}, lambda r: r == {"deleted": True}),
    "space_owners_bind": (
        lambda c, d: c.space_owners.bind("ow", "s1", unbind_existing_owners=True, dry_run=d), "POST",
        "/space-owners/ow/bind/s1", {"unbindExistingOwners": True}, {"id": "ow"}, lambda r: r.id == "ow"),
    "space_owners_unbind": (
        lambda c, d: c.space_owners.unbind("ow", "s1", dry_run=d), "POST", "/space-owners/ow/unbind/s1", None,
        {"id": "ow"}, lambda r: r.id == "ow"),
    "categories_create": (
        lambda c, d: c.categories.create(CategoryCreate(set_id="set", name="Окна"), dry_run=d), "POST",
        "/categories", {"setId": "set", "name": "Окна"}, {"id": "cat"}, lambda r: r.id == "cat"),
    "check_lists_set_status": (
        lambda c, d: c.check_lists.set_status("cl", CheckRecordStatus.ACCEPTED, space_id="s1",
                                              stage=Stage.ACCEPTANCE, dry_run=d),
        "POST", "/check-lists/cl/set-status/accepted?spaceId=s1&stage=acceptance", None,
        {"statusName": "Принято"}, lambda r: r.status_name == "Принято"),
    "check_lists_set_item_status": (
        lambda c, d: c.check_lists.set_item_status("cl", "ci", CheckRecordStatus.REJECTED, space_id="s1",
                                                   stage=Stage.ACCEPTANCE, dry_run=d),
        "POST", "/check-lists/cl/set-item-status/rejected?spaceId=s1&checkItemId=ci&stage=acceptance", None,
        {"id": "ci"}, lambda r: r.id == "ci"),
    "checks_create": (
        lambda c, d: c.checks.create(CheckCreate(object_id=O, description="обход"), dry_run=d), "POST",
        "/checks", {"objectId": O, "description": "обход", "attachments": []}, {"id": "ch"},
        lambda r: r.id == "ch"),
    "comments_create": (
        lambda c, d: c.comments.create(CommentCreate(comment_type_id=CommentType.PROBLEM_COMMENT,
                                                     links=CommentLinksInput(problem_id="p1"),
                                                     description="Исправлено"), dry_run=d),
        "POST", "/comments",
        {"commentTypeId": "problem-comment", "links": {"problemId": "p1"}, "official": False,
         "description": "Исправлено"},
        {"id": "cm", "number": None}, lambda r: r.id == "cm"),
    "work_acceptances_edit": (
        lambda c, d: c.work_acceptances.edit("w1", WorkAcceptanceEdit(percent=80), dry_run=d), "POST",
        "/work-acceptances/w1", {"percent": 80.0}, {"id": "w1"}, lambda r: r.id == "w1"),
    "work_acceptances_create_many": (
        lambda c, d: c.work_acceptances.create_many(
            [WorkAcceptanceCreate(type=WorkAcceptanceType.VISIBLE, front_type=FrontType.SPACES, object_id=O,
                                  space_ids=["s1"], acceptance_interval_start=T, external_id="ext-1")], dry_run=d),
        "POST", "/work-acceptances",
        [{"type": "visible", "frontType": "spaces", "objectId": O, "spaceIds": ["s1"],
          "acceptanceIntervalStart": MS, "externalId": "ext-1"}],
        [{"id": "w9", "externalId": "ext-1", "error": False},
         {"id": None, "externalId": "ext-2", "error": True, "errorDescription": "нет вида работ"}],
        lambda r: [x.error for x in r] == [False, True] and r[1].error_description == "нет вида работ"),
    "internal_acceptances_create": (
        lambda c, d: c.internal_acceptances.create(InternalAcceptanceCreate(object_id=O, space_id="s1"), dry_run=d),
        "POST", "/internal-acceptances", {"objectId": O, "spaceId": "s1", "attachments": []}, {"id": "ia"},
        lambda r: r.id == "ia"),
    "owner_acceptances_create": (
        lambda c, d: c.owner_acceptances.create(
            OwnerAcceptanceCreate(space_id="s1", object_id=O, resolution=OwnerAcceptanceResolution.ACCEPTED),
            dry_run=d),
        "POST", "/owner-acceptances", {"spaceId": "s1", "objectId": O, "resolution": "accepted"}, "oa-new",
        lambda r: r == "oa-new"),
    "owner_acceptances_set_status": (
        lambda c, d: c.owner_acceptances.set_status("oa", OwnerAcceptanceStatus.DONE, dry_run=d), "POST",
        "/owner-acceptances/oa/edit-status/done", None, {"id": "oa"}, lambda r: r.id == "oa"),
    "owner_acceptances_set_resolution": (
        lambda c, d: c.owner_acceptances.set_resolution("oa", OwnerAcceptanceResolution.REJECTED, dry_run=d),
        "POST", "/owner-acceptances/oa/edit-resolutions/rejected", None, {"id": "oa"}, lambda r: r.id == "oa"),
    "warranty_claims_create": (
        lambda c, d: c.warranty_claims.create(WarrantyClaimCreate(space_id="s1", object_id=O, description="течь"),
                                              dry_run=d),
        "POST", "/warranty-claims", {"spaceId": "s1", "objectId": O, "description": "течь"},
        {"id": "wc", "status": "waiting", "link": "/x"}, lambda r: r.status == "waiting"),
    "problems_create": (
        lambda c, d: c.problems.create(ProblemCreate(
            object_id=O, stage=Stage.TRANSFER, process_id=ProcessId.UNITS_HANDOVER, category_id="cat",
            links=ProblemLinksInput(space_id="s1"), reason=ReasonInput(value="СП 71"), planned_fix_date=T,
            description="Скол"), dry_run=d),
        "POST", "/problems",
        {"objectId": O, "stage": "transfer", "processId": "units-handover", "categoryId": "cat",
         "links": {"spaceId": "s1"}, "reason": {"value": "СП 71"}, "plannedFixDate": MS, "description": "Скол"},
        {"id": "p9", "number": 1}, lambda r: r.id == "p9"),
    "problems_edit": (
        lambda c, d: c.problems.edit("p1", ProblemEdit(status=ProblemStatus.FIXED), dry_run=d), "POST",
        "/problems/p1", {"status": "fixed"}, {"id": "p1"}, lambda r: r.id == "p1"),
    "tasks_create": (
        lambda c, d: c.tasks.create(TaskCreate(name="Проверить", object_id=O, task_priority_id=TaskPriority.HIGH,
                                               task_type_id=TaskType.CHECK), dry_run=d),
        "POST", "/tasks", {"name": "Проверить", "objectId": O, "taskPriorityId": "high", "taskTypeId": "check"},
        {"id": "t9"}, lambda r: r.id == "t9"),
    "tasks_edit": (
        lambda c, d: c.tasks.edit("t1", TaskEdit(floor="5"), dry_run=d), "POST", "/tasks/t1", {"floor": "5"},
        {"id": "t1"}, lambda r: r.id == "t1"),
}

MUTATING = sorted(op.tool_name for op in REGISTRY.all() if op.kind != "R")


def test_every_mutating_operation_has_case() -> None:
    assert len(MUTATING) == 24
    assert MUTATING == sorted(CASES)


def _norm(url: str) -> URL:
    u = URL(url)
    return u.with_query(sorted(u.query.items()))


@pytest.fixture
async def client():  # type: ignore[no-untyped-def]
    async with TehzorClient(api_key="k", rate_limit=0) as thz:
        yield thz


@pytest.mark.parametrize("tool", sorted(CASES))
async def test_write_operation(tool: str, client: TehzorClient, mocked: aioresponses) -> None:
    call, method, path, body, payload, check = CASES[tool]
    url = f"{BASE}{path}"
    mocked.add(url, method=method, payload=payload)
    result = await call(client, False)
    assert check(result)
    reqs = [r for (m, u), rs in mocked.requests.items() if m == method and _norm(str(u)) == _norm(url) for r in rs]
    assert len(reqs) == 1, list(mocked.requests)
    assert reqs[0].kwargs.get("json") == body


@pytest.mark.parametrize("tool", sorted(CASES))
async def test_dry_run_sends_nothing(tool: str, client: TehzorClient, mocked: aioresponses) -> None:
    call, method, path, body, _, _ = CASES[tool]
    prepared = await call(client, True)
    assert isinstance(prepared, PreparedRequest)
    assert not mocked.requests
    assert prepared.method == method
    assert _norm(prepared.describe().split(" ", 1)[1]) == _norm(path)
    assert prepared.json == body
    assert prepared.kind in ("W", "D")


@pytest.mark.parametrize("tool", sorted(CASES))
async def test_read_only_blocks_before_network(tool: str, mocked: aioresponses) -> None:
    async with TehzorClient(api_key="k", rate_limit=0, read_only=True) as thz:
        with pytest.raises(ReadOnlyError):
            await CASES[tool][0](thz, False)
    assert not mocked.requests


NON_IDEMPOTENT = sorted(op.tool_name for op in REGISTRY.all() if op.kind != "R" and not op.idempotent)


def test_creates_and_delete_are_not_idempotent() -> None:
    assert NON_IDEMPOTENT == sorted(
        [n for n in CASES if n.endswith(("_create", "_create_many", "_get_or_create")) or n == "space_owners_delete"]
    )


@pytest.mark.parametrize("tool", NON_IDEMPOTENT)
async def test_non_idempotent_not_retried(tool: str, client: TehzorClient, mocked: aioresponses) -> None:
    call, method, path, _, payload, _ = CASES[tool]
    url = f"{BASE}{path}"
    mocked.add(url, method=method, status=503)
    mocked.add(url, method=method, payload=payload)
    with pytest.raises(ServerError):
        await call(client, False)
    assert sum(len(rs) for (m, u), rs in mocked.requests.items() if m == method) == 1


async def test_idempotent_edit_retried(clock: Any, mocked: aioresponses) -> None:
    from tehzor._transport import Transport

    t = Transport(api_key="k", rate_limit=0, clock=clock, sleep=clock.sleep)
    async with TehzorClient(transport=t) as thz:
        mocked.post(f"{BASE}/problems/p1", status=503)
        mocked.post(f"{BASE}/problems/p1", payload={"id": "p1"})
        assert (await thz.problems.edit("p1", ProblemEdit(description="x"))).id == "p1"


# --- валидация до отправки -----------------------------------------------------------------------


def test_invalid_enum_rejected_before_network() -> None:
    with pytest.raises(ValidationError):
        ProblemCreate(object_id=O, stage="unknown-stage", process_id=ProcessId.AUDIT)  # type: ignore[arg-type]


def test_warranty_claim_requires_space_and_object() -> None:
    with pytest.raises(ValidationError, match="space_id или space_number"):
        WarrantyClaimCreate(object_id=O)
    with pytest.raises(ValidationError, match="object_id или object_name"):
        WarrantyClaimCreate(space_number="12")
    assert WarrantyClaimCreate(space_number="12", object_name="Дом").to_api() == {
        "spaceNumber": "12", "objectName": "Дом"}


def test_space_edit_area_bti_regression() -> None:
    """Старая модель SpaceUpdate молча теряла area_bti."""
    assert SpaceEdit(area_bti=55.1, number_bti="7", floor_bti="3").to_api() == {
        "areaBTI": 55.1, "numberBTI": "7", "floorBTI": "3"}
    assert SpaceEdit.model_validate({"areaBTI": 1}).area_bti == 1


def test_request_rejects_unknown_field() -> None:
    with pytest.raises(ValidationError):
        TaskEdit(nmae="опечатка")  # type: ignore[call-arg]
