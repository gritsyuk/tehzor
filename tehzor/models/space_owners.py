"""Собственники помещений. Чтения в API нет; запись проверена в песочнице (tests/sandbox, уровень 1)."""

from __future__ import annotations

from ._base import TehzorModel, TehzorRequest


class SpaceOwner(TehzorModel):
    """Собственник.

    spec: ответ на создание — CreatableSpaceOwner без id; fact (2026-11-04, песочница): id приходит
    в ответах create/edit/get_or_create, есть `companyId` (нет в spec). id оставлен необязательным на случай
    расхождения с spec.
    """

    id: str | None = None
    company_id: str | None = None
    name: str | None = None
    email: str | None = None
    additional_email: str | None = None
    phone: str | None = None
    additional_phone: str | None = None
    comment: str | None = None
    spaces: list[str] | None = None


class SpaceOwnerCreate(TehzorRequest):
    """Тело `POST /space-owners`. spec: `spaces.items: array` — ошибка схемы, на деле список id."""

    name: str
    email: str | None = None
    additional_email: str | None = None
    phone: str | None = None
    additional_phone: str | None = None
    comment: str | None = None
    spaces: list[str] | None = None


class SpaceOwnerEdit(TehzorRequest):
    """Тело `POST /space-owners/{id}`."""

    name: str | None = None
    email: str | None = None
    additional_email: str | None = None
    phone: str | None = None
    additional_phone: str | None = None
    comment: str | None = None
    spaces: list[str] | None = None


class SpaceOwnerGetOrCreate(TehzorRequest):
    """Тело `POST /space-owners/get-or-create`."""

    name: str
    email: str | None = None
    phone: str | None = None
