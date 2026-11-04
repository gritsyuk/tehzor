"""Собственники помещений. Чтения в API нет — проверяются только на заглушках."""

from __future__ import annotations

from ._base import TehzorModel, TehzorRequest


class SpaceOwner(TehzorModel):
    id: str
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
