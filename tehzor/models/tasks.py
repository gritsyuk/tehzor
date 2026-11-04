"""Задачи. Сверено с живым API 2026-11-04."""

from __future__ import annotations

from ..enums import LocationType, TaskPriority, TaskStatus, TaskType
from ..types import Timestamp
from ._base import TehzorModel, TehzorRequest
from .common import AttachmentList, ExternalRef, NamedRef, User


class TaskLinks(TehzorModel):
    space_ids: list[str] | None = None
    work_acceptance_id: str | None = None
    check_list_id: str | None = None
    check_item_id: str | None = None
    problem_id: str | None = None


class Task(TehzorModel):
    """fact: есть `name` и `createdFromEntity` (нет в спецификации ответа); в деталях у пользователей
    нет `fullName`; `planId`, `floor` в выборке не встречались."""

    id: str
    name: str | None = None
    description: str | None = None
    object: ExternalRef | None = None
    status: NamedRef | None = None
    task_priority: NamedRef | None = None
    task_type: NamedRef | None = None
    task_interval_start: Timestamp | None = None
    task_interval_end: Timestamp | None = None
    resp_users: list[User | str] | None = None
    active_group: str | None = None
    active_group_leader: User | None = None
    initial_group: str | None = None
    initial_group_leader: User | None = None
    plan_id: str | None = None
    floor: str | None = None
    attachments: AttachmentList | None = None
    links: TaskLinks | None = None
    created_from_entity: str | None = None
    created_at: Timestamp | None = None
    created_by: User | None = None
    modified_at: Timestamp | None = None
    modified_by: User | None = None
    link: str | None = None


class TaskFilters(TehzorRequest):
    """Тело `POST /tasks/get-tasks`. Указывайте `objects`."""

    objects: list[str] | None = None
    created_at_from: Timestamp | None = None
    created_at_to: Timestamp | None = None
    modified_at_from: Timestamp | None = None
    modified_at_to: Timestamp | None = None


class TaskLinksInput(TehzorRequest):
    space_ids: list[str] | None = None
    work_acceptance_id: str | None = None
    check_list_id: str | None = None
    check_item_id: str | None = None
    problem_id: str | None = None


class _TaskBody(TehzorRequest):
    description: str | None = None
    status_id: TaskStatus | None = None
    location_type: LocationType | None = None
    task_interval_start: Timestamp | None = None
    task_interval_end: Timestamp | None = None
    resp_user_ids: list[str] | None = None
    active_group_id: str | None = None
    plan_id: str | None = None
    floor: str | None = None
    attachments: list[str] | None = None
    links: TaskLinksInput | None = None


class TaskCreate(_TaskBody):
    """Тело `POST /tasks`. Проверяется только на заглушках."""

    name: str
    object_id: str
    task_priority_id: TaskPriority
    task_type_id: TaskType


class TaskEdit(_TaskBody):
    """Тело `POST /tasks/{id}`. Проверяется только на заглушках."""

    name: str | None = None
    task_priority_id: TaskPriority | None = None
    task_type_id: TaskType | None = None
