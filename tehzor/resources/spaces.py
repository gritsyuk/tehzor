"""Помещения (spaces). Изменяющие методы — этап 4."""

from __future__ import annotations

import builtins
from collections.abc import AsyncIterator, Sequence

from .._pagination import DEFAULT_PAGE_SIZE, iter_pages
from .._registry import operation
from ..enums import DecorationSetField, OwnerAcceptanceField, WarrantyClaimField
from ..models.spaces import (
    ContractForm,
    DecorationSet,
    MeterType,
    Space,
    SpaceFilters,
    SpaceMeter,
    SpaceOwnerAcceptanceBrief,
    SpaceStatus,
    SpaceStatusSet,
    SpaceType,
    SpaceWarrantyClaimBrief,
)
from ._base import BaseResource, body, warn_without_objects


class SpacesResource(BaseResource):
    resource_name = "spaces"

    @operation("SpacesController_getSpaces", "POST", "/spaces/get-spaces", paginated=True,
               summary="Возвращает страницу помещений по фильтрам (укажите objects)")
    async def list(self, filters: SpaceFilters | None = None, *, limit: int = DEFAULT_PAGE_SIZE,
                   offset: int = 0) -> builtins.list[Space]:
        warn_without_objects(filters.objects or filters.spaces if filters else None, "spaces.list")
        return await self._many("list", Space, params={"limit": limit, "offset": offset},
                                json=body(filters) or {})

    async def iter(self, filters: SpaceFilters | None = None, *, page_size: int = DEFAULT_PAGE_SIZE,
                   max_items: int | None = None) -> AsyncIterator[Space]:
        async def fetch(limit: int, offset: int) -> builtins.list[Space]:
            return await self.list(filters, limit=limit, offset=offset)

        async for item in iter_pages(fetch, page_size=page_size, max_items=max_items):
            yield item

    @operation("SpacesController_getOne", "GET", "/spaces/{spaceId}",
               summary="Возвращает помещение по внутреннему или внешнему id")
    async def get(self, space_id: str) -> Space:
        return await self._one("get", Space, path_params={"spaceId": space_id})

    @operation("SpacesController_getStatus", "GET", "/spaces/{spaceId}/status", summary="Статус помещения")
    async def get_status(self, space_id: str) -> SpaceStatus:
        return await self._one("get_status", SpaceStatus, path_params={"spaceId": space_id})

    @operation("MetersController_getMeters", "GET", "/spaces/{spaceId}/meters",
               summary="Приборы учёта и показания помещения ([] если приборов нет)")
    async def meters(self, space_id: str) -> builtins.list[SpaceMeter]:
        # fact: «приборы не найдены» — 404 (а «помещение не найдено» — 400)
        return await self._many_or_empty("meters", SpaceMeter, path_params={"spaceId": space_id})

    @operation("OwnerAcceptancesController_getOwnerAcceptances", "GET", "/spaces/{spaceId}/owner-acceptances",
               summary="Передачи собственникам по помещению")
    async def owner_acceptances(self, space_id: str, fields: Sequence[OwnerAcceptanceField | str] | None = None
                                ) -> builtins.list[SpaceOwnerAcceptanceBrief]:
        return await self._many("owner_acceptances", SpaceOwnerAcceptanceBrief, path_params={"spaceId": space_id},
                                params={"fields": list(fields) if fields else None})

    @operation("WarrantyClaimsController_getWarrantyClaims", "GET", "/spaces/{spaceId}/warranty-claims",
               summary="Гарантийные обращения по помещению")
    async def warranty_claims(self, space_id: str, fields: Sequence[WarrantyClaimField | str] | None = None
                              ) -> builtins.list[SpaceWarrantyClaimBrief]:
        return await self._many("warranty_claims", SpaceWarrantyClaimBrief, path_params={"spaceId": space_id},
                                params={"fields": list(fields) if fields else None})

    @operation("SpaceTypesController_get", "GET", "/space-types", summary="Справочник типов помещений")
    async def types(self) -> builtins.list[SpaceType]:
        return await self._many("types", SpaceType)

    @operation("MeterTypesController_get", "GET", "/meter-types", summary="Справочник типов приборов учёта")
    async def meter_types(self) -> builtins.list[MeterType]:
        return await self._many("meter_types", MeterType)

    @operation("ContractFormsController_get", "GET", "/contract-forms", summary="Справочник форм договоров")
    async def contract_forms(self) -> builtins.list[ContractForm]:
        return await self._many("contract_forms", ContractForm)

    @operation("SpaceTypesDecorationsController_getSpaceTypesDecorations", "GET", "/space-types-decorations",
               summary="Наборы типов отделки")
    async def decoration_sets(
        self, fields: Sequence[DecorationSetField | str] | None = None
    ) -> builtins.list[DecorationSet]:
        data = await self._raw("decoration_sets", params={"fields": list(fields) if fields else None})
        # spec: один объект; fact: список — поддерживаем оба
        items = data if isinstance(data, list) else [data] if data else []
        return [DecorationSet.model_validate(x) for x in items]

    @operation("SpaceStatusesController_getSpaceStatuses", "GET", "/space-statuses",
               summary="Наборы статусов помещений")
    async def status_sets(self) -> builtins.list[SpaceStatusSet]:
        data = await self._raw("status_sets")
        items = data if isinstance(data, list) else [data] if data else []
        return [SpaceStatusSet.model_validate(x) for x in items]
