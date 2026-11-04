"""Нарушения. Сверено с живым API 2026-11-04 (docs/API_FACTS.md)."""

from __future__ import annotations

from typing import Any

from ..enums import ProblemStatus, ProcessId, Stage
from ..types import Timestamp
from ._base import TehzorModel, TehzorRequest
from .common import AttachmentList, ExternalRef, Location, NamedRef, Reason, User


class ProblemLinks(TehzorModel):
    """Связанные сущности. fact: приходят только заполненные ключи (spec: все 12 обязательны)."""

    space_id: str | None = None
    check_id: str | None = None
    internal_acceptance_id: str | None = None
    owner_acceptance_id: str | None = None
    warranty_claim_id: str | None = None
    check_list_id: str | None = None
    check_item_id: str | None = None
    check_record_id: str | None = None
    task_id: str | None = None
    template_id: str | None = None
    structure_id: str | None = None
    work_acceptance_id: str | None = None


class Problem(TehzorModel):
    """Нарушение (`GET /problems/{id}`, списки нарушений).

    fact: `attachments` — объекты (spec: строки); `inspectors` — `[{id}]`; `watchers` — `[str]`
    (spec: UserDto[]); есть `processId` (нет в spec); `space`, `plan`, `reason`, даты — только если заданы.
    fact: `GET /warranty-claims/{id}/problems` отдаёт сокращённую форму (id, number, status, description,
    plannedFixDate, categoryId) — она тоже разбирается этой моделью.
    """

    id: str
    external_id: str | None = None
    object: ExternalRef | None = None
    links: ProblemLinks | None = None
    space: ExternalRef | None = None
    stage: str | None = None
    process_id: str | None = None
    number: int | None = None
    status: NamedRef | None = None
    reopened_times: int | None = None
    planned_fix_date: Timestamp | None = None
    actual_fix_date: Timestamp | None = None
    category_id: str | None = None
    category: NamedRef | None = None
    problem_tags: list[NamedRef | str] | None = None
    plan: ExternalRef | None = None
    plan_image: str | None = None
    floor: str | None = None
    location: Location | None = None
    display_location: str | None = None
    reason: Reason | None = None
    description: str | None = None
    prescription: str | None = None
    attachments: AttachmentList | None = None
    performers: list[User | str] | None = None
    inspectors: list[User | str] | None = None
    watchers: list[User | str] | None = None
    performers_active_group: str | None = None
    performers_active_group_leader: User | None = None
    performers_initial_group: str | None = None
    performers_initial_group_leader: User | None = None
    inspectors_active_group: str | None = None
    critical: bool | None = None
    local_created_at: Timestamp | None = None
    created_at: Timestamp | None = None
    created_by: User | None = None
    modified_at: Timestamp | None = None
    modified_by: User | None = None
    custom_fields: dict[str, Any] | None = None


class ProblemFilters(TehzorRequest):
    """Тело `POST /problems/get-problems`.

    Указывайте `objects`: fact — без фильтра запрос даёт 502 примерно через 30 с.
    `modified_at_from/to`: spec — строка; формат на живом API ещё не подтверждён.
    """

    objects: list[str] | None = None
    include_objects_children: bool | None = None
    spaces: list[str] | None = None
    modified_at_from: str | int | None = None
    modified_at_to: str | int | None = None
    statuses: list[ProblemStatus | str] | None = None


class ReasonInput(TehzorRequest):
    value: str | None = None
    regulatory_standard: str | None = None


class LocationInput(TehzorRequest):
    sectors: list[str] | None = None
    points: list[str] | None = None
    map_points: list[str] | None = None


class ProblemLinksInput(TehzorRequest):
    space_id: str | None = None
    check_id: str | None = None
    internal_acceptance_id: str | None = None
    owner_acceptance_id: str | None = None
    warranty_claim_id: str | None = None
    check_list_id: str | None = None
    check_item_id: str | None = None
    check_record_id: str | None = None
    task_id: str | None = None
    template_id: str | None = None
    structure_id: str | None = None
    work_acceptance_id: str | None = None


class _ProblemBody(TehzorRequest):
    links: ProblemLinksInput | None = None
    external_id: str | None = None
    category_id: str | None = None
    planned_fix_date: Timestamp | None = None
    reason: ReasonInput | None = None
    description: str | None = None
    prescription: str | None = None
    attachments: list[str] | None = None
    plan_id: str | None = None
    floor: str | None = None
    location: LocationInput | None = None
    critical: bool | None = None
    performers: list[str] | None = None
    performers_active_group: str | None = None
    inspectors: list[str] | None = None
    inspectors_active_group: str | None = None
    watchers: list[str] | None = None
    problem_tags: list[str] | None = None
    custom_fields: dict[str, Any] | None = None


class ProblemCreate(_ProblemBody):
    """Тело `POST /problems`. Проверяется только на заглушках."""

    object_id: str
    stage: Stage
    process_id: ProcessId
    created_by: str | None = None


class ProblemEdit(_ProblemBody):
    """Тело `POST /problems/{id}`. Проверяется только на заглушках."""

    stage: Stage | None = None
    process_id: ProcessId | None = None
    status: ProblemStatus | None = None
    modified_by: str | None = None


class ProblemReply(TehzorModel):
    """Последний официальный ответ (`GET /problems/{id}/reply`).

    fact: это комментарий — есть `ancestors`, `number`, `official`; attachments — объекты.
    fact: если ответа нет, API отвечает 404, клиент возвращает None.
    """

    id: str
    object_id: str | None = None
    problem_id: str | None = None
    links: ProblemLinks | None = None
    stage: str | None = None
    number: int | None = None
    official: bool | None = None
    ancestors: list[str] | None = None
    description: str | None = None
    attachments: AttachmentList | None = None
    created_by: User | None = None
    created_at: Timestamp | None = None
    modified_by: User | None = None
    modified_at: Timestamp | None = None


__all__ = [
    "Problem",
    "ProblemCreate",
    "ProblemEdit",
    "ProblemFilters",
    "ProblemLinks",
    "ProblemLinksInput",
    "ProblemReply",
]
