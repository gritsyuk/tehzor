"""Общие вложенные модели. Сверено с живым API 2026-11-04 (docs/API_FACTS.md)."""

from __future__ import annotations

from typing import Any

from pydantic import AliasChoices, Field

from ._base import TehzorModel


def id_field() -> Any:
    """Обязательный id, принимающий и `id`, и `_id`."""
    return Field(validation_alias=AliasChoices("id", "_id"), serialization_alias="id")


class NamedRef(TehzorModel):
    """Ссылка {id, name}: статусы, виды работ, метки, справочники.

    spec: в DTO передач собственникам id называется `_id`; fact: приходит `id`. Принимаются оба.
    """

    id: str = id_field()
    name: str | None = None


class ExternalRef(NamedRef):
    """{id, name, externalId}: объект, помещение, план в нарушении."""

    external_id: str | None = None


class DictItem(NamedRef):
    """Элемент справочника (статусы, типы, решения)."""


class User(TehzorModel):
    """Пользователь.

    fact: набор полей зависит от эндпоинта — в `inspectors` только `{id}`, в приёмке работ `{id, fullName}`,
    в задаче без `fullName`; есть `color` и `employers`, которых нет в UserDto.
    """

    id: str = id_field()
    full_name: str | None = None
    display_name: str | None = None
    position: str | None = None
    color: str | None = None
    employers: list[Any] | None = None


class FileVariant(TehzorModel):
    id: str | None = None
    name: str | None = None
    size: int | None = None
    type: str | None = None
    url: str | None = None


class Attachment(TehzorModel):
    """Вложение.

    spec: `attachments: string[]`; fact: `[{id, full: {...}, preview?: {...}}]`.
    """

    id: str
    full: FileVariant | None = None
    preview: FileVariant | None = None


AttachmentList = list[Attachment | str]
"""fact: объекты; spec: строки. Принимаются оба варианта."""


class Location(TehzorModel):
    sectors: list[Any] | None = None
    points: list[Any] | None = None
    map_points: list[Any] | None = None


class Reason(TehzorModel):
    """Основание нарушения. fact: `regulatoryStandard` бывает не всегда."""

    value: str | None = None
    regulatory_standard: str | None = None
