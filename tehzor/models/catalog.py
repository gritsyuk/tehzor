"""Виды работ, метки, чек-листы, проверки. Сверено с живым API 2026-11-04."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from ..types import Timestamp
from ._base import TehzorModel, TehzorRequest
from .common import AttachmentList, NamedRef, User

# --- виды работ -----------------------------------------------------------------------------------


class Category(TehzorModel):
    """fact: `externalId`, `parentId`, `modifiedBy` есть не всегда."""

    id: str
    name: str | None = None
    categories_set_id: str | None = None
    order: float | None = None
    external_id: str | None = None
    parent_id: str | None = None
    created_at: Timestamp | None = None
    created_by: User | None = None
    modified_at: Timestamp | None = None
    modified_by: User | None = None


class CategoriesSet(TehzorModel):
    """fact: есть `shared` (нет в спецификации); `externalId` в выборке не встречался."""

    id: str
    external_id: str | None = None
    name: str | None = None
    objects: list[str] | None = None
    stages: list[str] | None = None
    shared: bool | None = None


class CategoryCreate(TehzorRequest):
    """Тело `POST /categories`. Проверяется только на заглушках."""

    set_id: str
    name: str
    external_id: str | None = None
    order: float | None = None
    parent_id: str | None = None


# --- метки ----------------------------------------------------------------------------------------


class Tag(TehzorModel):
    id: str
    name: str | None = None
    color: str | None = None
    problem_tags_set_id: str | None = None
    created_at: Timestamp | None = None
    modified_at: Timestamp | None = None


class TagsSet(TehzorModel):
    id: str
    name: str | None = None
    company_id: str | None = None
    objects: list[str] | None = None
    stages: list[str] | None = None
    created_at: Timestamp | None = None
    modified_at: Timestamp | None = None


# --- чек-листы ------------------------------------------------------------------------------------


class CheckList(TehzorModel):
    """fact: `frontType` есть не всегда, `structureType` в выборке не встречался."""

    id: str
    name: str | None = None
    company_id: str | None = None
    objects: list[NamedRef] | None = None
    stage: str | None = None
    space_types: list[str] | None = None
    structure_type: str | None = None
    process_id: str | None = None
    type_decoration: list[NamedRef] | None = None
    categories: list[NamedRef] | None = None
    front_type: str | None = None


class CheckItem(TehzorModel):
    """fact: `parent` есть не всегда; `externalId`, `customFields` в выборке не встречались."""

    id: str
    name: str | None = None
    description: str | None = None
    dependencies: list[NamedRef | str] | None = None
    parent: NamedRef | None = None
    external_id: str | None = None
    custom_fields: dict[str, Any] | None = None


class CheckListWithItems(CheckList):
    check_items: list[CheckItem] | None = None


class CheckListStatus(TehzorModel):
    """`GET /check-lists/status`: у ответа нет id."""

    check_list_name: str | None = None
    status_name: str | None = None


class CheckItemStatus(TehzorModel):
    id: str
    check_item_name: str | None = None
    check_list_name: str | None = None  # fact: нет в spec
    external_id: str | None = None
    parent_id: str | None = None
    check_list_id: str | None = None
    status_name: str | None = None
    custom_fields: dict[str, Any] | None = None


# --- проверки -------------------------------------------------------------------------------------


class CheckLinks(TehzorModel):
    space_id: str | None = None
    structure_id: str | None = None
    check_list_id: str | None = None
    check_item_id: str | None = None
    check_record_id: str | None = None


class Check(TehzorModel):
    """fact: `links` может быть пустым объектом; `description` в выборке не встречался."""

    id: str
    object_id: str | None = None
    links: CheckLinks | None = None
    stage: str | None = None
    number: int | None = None
    description: str | None = None
    attachments: AttachmentList | None = None
    created_at: Timestamp | None = None
    modified_at: Timestamp | None = None


class CheckCreate(TehzorRequest):
    """Тело `POST /checks`. Проверяется только на заглушках."""

    object_id: str
    space_id: str | None = None
    structure_id: str | None = None
    description: str | None = None
    attachments: list[str] = Field(default_factory=list)
