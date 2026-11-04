"""Помещения, приборы учёта, справочники помещений. Сверено с живым API 2026-11-04."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from ..types import Timestamp
from ._base import TehzorModel, TehzorRequest
from .common import AttachmentList, DictItem, NamedRef, User


class SpaceType(TehzorModel):
    id: str
    name: str | None = None
    singular_name: str | None = None


class SpaceStatus(TehzorModel):
    id: str
    name: str | None = None
    stage: str | None = None


class SpaceTypeDecoration(TehzorModel):
    id: str
    name: str | None = None


class Space(TehzorModel):
    """Помещение (`GET /spaces/{id}`, элементы `POST /spaces/get-spaces`).

    fact: пустые поля сервер не отдаёт; в списке приходят только id, objectId, name, floor, type, status.
    fact: `typeDecoration` — объект {id, name} (подтверждено), в запросе изменения — строка-id.
    fact: `customFields` отсутствует, хотя в спецификации обязателен.
    """

    id: str
    external_id: str | None = None
    object_id: str | None = None
    name: str | None = None
    alt_name: str | None = None
    type: SpaceType | None = None
    status: SpaceStatus | None = None
    indicators: list[str] | None = None
    floor: str | None = None
    planned_area: float | None = None
    actual_area: float | None = None
    type_decoration: SpaceTypeDecoration | str | None = None
    area_bti: float | None = Field(default=None, alias="areaBTI")
    number_bti: str | None = Field(default=None, alias="numberBTI")
    floor_bti: str | None = Field(default=None, alias="floorBTI")
    contract_form: Any = None
    markup_for_registration: Any = None
    created_by: User | None = None
    created_at: Timestamp | None = None
    modified_by: User | None = None
    modified_at: Timestamp | None = None
    decoration_warranty_expired_date: Timestamp | None = None
    constructive_warranty_expired_date: Timestamp | None = None
    technical_equipment_warranty_expired_date: Timestamp | None = None
    custom_fields: dict[str, Any] | None = None


class SpaceFilters(TehzorRequest):
    """Тело `POST /spaces/get-spaces`. Указывайте `objects`: без фильтра запрос тяжёлый."""

    objects: list[str] | None = None
    spaces: list[str] | None = None
    include_objects_children: bool | None = None


class SpaceEdit(TehzorRequest):
    """Тело `POST /spaces/{id}`. Отправляются только заданные поля."""

    external_id: str | None = None
    alt_name: str | None = None
    planned_area: float | None = None
    actual_area: float | None = None
    type_decoration: str | None = None
    """id типа отделки (см. `spaces.decoration_sets()`)."""
    area_bti: float | None = Field(default=None, alias="areaBTI")
    number_bti: str | None = Field(default=None, alias="numberBTI")
    floor_bti: str | None = Field(default=None, alias="floorBTI")
    contract_form: str | None = None
    """dkp / ddu (см. `spaces.contract_forms()`)."""
    markup_for_registration: bool | None = None
    modified_by: str | None = None
    decoration_warranty_expired_date: Timestamp | None = None
    constructive_warranty_expired_date: Timestamp | None = None
    technical_equipment_warranty_expired_date: Timestamp | None = None
    custom_fields: dict[str, Any] | None = None


class MeterType(TehzorModel):
    id: str
    name: str | None = None
    measure_unit: str | None = None


class MeterConsumption(TehzorModel):
    id: str
    value: str | None = None
    tariff: NamedRef | None = None
    created_by: User | None = None
    created_at: Timestamp | None = None
    modified_by: User | None = None
    modified_at: Timestamp | None = None


class SpaceMeter(TehzorModel):
    """Прибор учёта. fact: при отсутствии приборов API отвечает 404, клиент возвращает []."""

    id: str
    type: MeterType | None = None
    serial_number: str | None = None
    description: str | None = None
    consumptions: list[MeterConsumption] | None = None
    created_by: User | None = None
    created_at: Timestamp | None = None
    modified_by: User | None = None
    modified_at: Timestamp | None = None


class ContractForm(DictItem):
    pass


class DecorationType(TehzorModel):
    id: str
    name: str | None = None
    space_types: list[str] | None = None
    type_decoration_set_id: str | None = None


class DecorationSet(TehzorModel):
    """Набор типов отделки. spec: ответ — один объект, а элементы — строки; fact: список объектов."""

    id: str
    name: str | None = None
    space_types_decorations: list[DecorationType | str] | None = None


class SpaceStatusSet(TehzorModel):
    """Набор статусов помещений. spec: один объект; fact: список."""

    id: str
    name: str | None = None
    space_statuses: list[SpaceStatus] | None = None


class SpaceOwnerAcceptanceBrief(TehzorModel):
    """Элемент `GET /spaces/{id}/owner-acceptances`. fact: `status` и `spaceOwnerId` могут отсутствовать."""

    id: str
    number: int | None = None
    resolution: NamedRef | None = None
    status: NamedRef | None = None
    space_owner_id: str | None = None
    attachments: AttachmentList | None = None
    created_at: Timestamp | None = None
    modified_at: Timestamp | None = None


class SpaceWarrantyClaimBrief(TehzorModel):
    """Элемент `GET /spaces/{id}/warranty-claims`.

    fact: здесь `status` — объект, а в `GET /warranty-claims/{id}` — строка."""

    id: str
    number: int | None = None
    status: NamedRef | None = None
    attachments: AttachmentList | None = None
    created_at: Timestamp | None = None
    modified_at: Timestamp | None = None
