"""Приёмки работ. Сверено с живым API 2026-11-04.

fact: это отдельная сущность, а не разновидность нарушения (старая модель наследовалась от Problem).
fact: поля `acceptanceDate` нет — есть `acceptanceIntervalStart/End` и `actualAcceptanceDate`.
"""

from __future__ import annotations

from typing import Any

from ..enums import FrontType, WorkAcceptanceStatus, WorkAcceptanceType
from ..types import Timestamp
from ._base import TehzorModel, TehzorRequest
from .common import AttachmentList, ExternalRef, NamedRef, User


class WorkScope(TehzorModel):
    """fact: часто пустой объект `{}` или только часть полей."""

    value: str | None = None
    unit_id: str | None = None
    unit_name: str | None = None


class WorkAcceptance(TehzorModel):
    """fact: в списке есть `acceptors`, в `GET /work-acceptances/{id}` — нет, зато есть `*Leader`,
    `createdBy`/`modifiedBy` (только id и fullName). `reopenedTimes` нет в спецификации.
    `contractor`, `percent`, `customFields` в выборке не встречались."""

    id: str
    object_id: str | None = None
    category: ExternalRef | None = None
    structure_ids: list[str] | None = None
    space_ids: list[str] | None = None
    acceptors: list[User | str] | None = None
    acceptors_active_group: str | None = None
    acceptors_active_group_leader: User | None = None
    acceptors_initial_group: str | None = None
    acceptors_initial_group_leader: User | None = None
    number: int | None = None
    status: NamedRef | None = None
    acceptance_interval_start: Timestamp | None = None
    acceptance_interval_end: Timestamp | None = None
    actual_acceptance_date: Timestamp | None = None
    percent: float | None = None
    comment: str | None = None
    description: str | None = None
    work_scope: str | None = None
    physical_work_scope: WorkScope | None = None
    plan_physical_work_scope: WorkScope | None = None
    contractor: NamedRef | None = None
    stage: str | None = None
    type: str | None = None
    front_type: str | None = None
    reopened_times: int | None = None
    attachments: AttachmentList | None = None
    custom_fields: dict[str, Any] | None = None
    created_at: Timestamp | None = None
    created_by: User | None = None
    modified_at: Timestamp | None = None
    modified_by: User | None = None


class WorkAcceptanceFilters(TehzorRequest):
    """Тело `POST /work-acceptances/get-work-acceptances` (объект передаётся query-параметром objectId)."""

    work_acceptance_ids: list[str] | None = None
    created_at_from: Timestamp | None = None
    created_at_to: Timestamp | None = None
    modified_at_from: Timestamp | None = None
    modified_at_to: Timestamp | None = None
    status: WorkAcceptanceStatus | None = None


class WorkScopeInput(TehzorRequest):
    value: str | None = None
    unit_id: str | None = None
    unit_name: str | None = None


class _WorkAcceptanceBody(TehzorRequest):
    category_id: str | None = None
    category_external_id: str | None = None
    description: str | None = None
    acceptance_interval_start: Timestamp | None = None
    acceptance_interval_end: Timestamp | None = None
    actual_acceptance_date: Timestamp | None = None
    structure_ids: list[str] | None = None
    external_structure_ids: list[str] | None = None
    space_ids: list[str] | None = None
    external_space_ids: list[str] | None = None
    work_scope: str | None = None
    plan_physical_work_scope: WorkScopeInput | None = None
    custom_fields: dict[str, Any] | None = None


class WorkAcceptanceCreate(_WorkAcceptanceBody):
    """Элемент тела `POST /work-acceptances` (массовое создание). Проверяется только на заглушках."""

    type: WorkAcceptanceType
    front_type: FrontType
    object_id: str | None = None
    external_object_id: str | None = None
    external_id: str | None = None
    link: str | None = None


class WorkAcceptanceEdit(_WorkAcceptanceBody):
    """Тело `POST /work-acceptances/{id}`. Проверяется только на заглушках."""

    type: WorkAcceptanceType | None = None
    front_type: FrontType | None = None
    percent: float | None = None
    status: WorkAcceptanceStatus | None = None
    attachments: list[str] | None = None


class WorkAcceptanceCreateResult(TehzorModel):
    """Результат массового создания: ошибка по элементу возвращается в `error`/`error_description`."""

    id: str | None = None
    external_id: str | None = None
    error: bool | None = None
    error_description: str | None = None
