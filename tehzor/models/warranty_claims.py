"""Гарантийные заявления. Сверено с живым API 2026-11-04."""

from __future__ import annotations

from typing import Any

from pydantic import model_validator

from ..types import Timestamp
from ._base import TehzorModel, TehzorRequest
from .common import AttachmentList, NamedRef


class WarrantyClaim(TehzorModel):
    """`GET /warranty-claims/{id}`.

    fact: `status` — строка (id статуса), а в `GET /spaces/{id}/warranty-claims` — объект {id, name};
    есть `registrationDate` (нет в спецификации); `customFields` в выборке не встречался.
    """

    id: str
    number: int | None = None
    status: NamedRef | str | None = None
    registration_date: Timestamp | None = None
    attachments: AttachmentList | None = None
    created_at: Timestamp | None = None
    modified_at: Timestamp | None = None
    custom_fields: dict[str, Any] | None = None
    link: str | None = None


class WarrantyClaimCreate(TehzorRequest):
    """Тело `POST /warranty-claims`. Нужно одно из spaceNumber/spaceId и одно из objectName/objectId.
    Проверяется только на заглушках."""

    owner_id: str | None = None
    claimer_name: str | None = None
    owner_name: str | None = None
    owner_email: str | None = None
    owner_phone: str | None = None
    space_number: str | None = None
    space_id: str | None = None
    object_id: str | None = None
    object_name: str | None = None
    description: str | None = None
    category_id: str | None = None
    attachments: list[str] | None = None
    custom_fields: dict[str, Any] | None = None

    @model_validator(mode="after")
    def _either_or(self) -> WarrantyClaimCreate:
        if not (self.space_id or self.space_number):
            raise ValueError("нужно указать space_id или space_number")
        if not (self.object_id or self.object_name):
            raise ValueError("нужно указать object_id или object_name")
        return self
