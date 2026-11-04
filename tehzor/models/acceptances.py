"""Внутренние приёмки и передачи собственникам. Сверено с живым API 2026-11-04."""

from __future__ import annotations

from pydantic import Field

from ..enums import OwnerAcceptanceResolution
from ..types import Timestamp
from ._base import TehzorModel, TehzorRequest
from .common import AttachmentList, NamedRef, User


class AcceptanceLinks(TehzorModel):
    space_id: str | None = None
    check_list_id: str | None = None
    check_item_id: str | None = None
    check_record_id: str | None = None


class InternalAcceptance(TehzorModel):
    """fact: в списке только id, objectId, number, stage, даты; `stage` нет в спецификации."""

    id: str
    object_id: str | None = None
    links: AcceptanceLinks | None = None
    number: int | None = None
    stage: str | None = None
    description: str | None = None
    attachments: AttachmentList | None = None
    created_at: Timestamp | None = None
    modified_at: Timestamp | None = None


class InternalAcceptanceCreate(TehzorRequest):
    """Тело `POST /internal-acceptances`. Проверяется только на заглушках."""

    object_id: str
    space_id: str | None = None
    description: str | None = None
    attachments: list[str] = Field(default_factory=list)


class OwnerAcceptance(TehzorModel):
    """Передача собственнику (`GET /owner-acceptances/{id}`).

    spec: status/resolution/spaceOwner с полем `_id`; fact: `resolution` = {id, name}, `status` и `spaceOwner`
    в выборке не встречались, есть `localId`.
    """

    id: str
    local_id: str | None = None
    object_id: str | None = None
    links: AcceptanceLinks | None = None
    number: int | None = None
    status: NamedRef | None = None
    resolution: NamedRef | None = None
    space_owner: NamedRef | None = None
    space_owner_id: str | None = None
    attachments: AttachmentList | None = None
    created_at: Timestamp | None = None
    created_by: User | None = None
    modified_at: Timestamp | None = None
    modified_by: User | None = None


class OwnerAcceptanceCreate(TehzorRequest):
    """Тело `POST /owner-acceptances`. Проверяется только на заглушках."""

    space_id: str
    object_id: str
    space_owner_id: str | None = None
    resolution: OwnerAcceptanceResolution | None = None
    attachments: list[str] | None = None
