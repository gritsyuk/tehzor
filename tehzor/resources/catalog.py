"""Виды работ, метки, чек-листы, проверки. Изменяющие методы — этап 4."""

from __future__ import annotations

import builtins

from .._registry import operation
from ..enums import Stage
from ..models.catalog import (
    CategoriesSet,
    Category,
    Check,
    CheckItemStatus,
    CheckList,
    CheckListStatus,
    CheckListWithItems,
    Tag,
    TagsSet,
)
from ..models.common import DictItem
from ._base import BaseResource


class CategoriesResource(BaseResource):
    resource_name = "categories"

    @operation("CategoriesController_get", "GET", "/categories", summary="Виды работ набора")
    async def list(self, set_id: str) -> builtins.list[Category]:
        return await self._many("list", Category, params={"setId": set_id})

    @operation("CategoriesSetsController_get", "GET", "/categories-sets", summary="Наборы видов работ")
    async def sets(self, object_id: str | None = None) -> builtins.list[CategoriesSet]:
        return await self._many("sets", CategoriesSet, params={"objectId": object_id})


class TagsResource(BaseResource):
    resource_name = "tags"

    @operation("TagsController_get", "GET", "/tags", summary="Метки набора")
    async def list(self, set_id: str) -> builtins.list[Tag]:
        return await self._many("list", Tag, params={"setId": set_id})

    @operation("TagsSetsController_get", "GET", "/tags-sets", summary="Наборы меток")
    async def sets(self, object_id: str | None = None) -> builtins.list[TagsSet]:
        return await self._many("sets", TagsSet, params={"objectId": object_id})


class CheckListsResource(BaseResource):
    resource_name = "check_lists"

    @operation("CheckListsController_getCheckLists", "GET", "/check-lists", summary="Чек-листы объекта")
    async def list(self, object_id: str | None = None, stage: Stage | str | None = None) -> builtins.list[CheckList]:
        return await self._many("list", CheckList, params={"objectId": object_id, "stage": stage})

    @operation("CheckListsController_getCheckList", "GET", "/check-lists/{checkListId}",
               summary="Чек-лист с категориями")
    async def get(self, check_list_id: str) -> CheckListWithItems:
        return await self._one("get", CheckListWithItems, path_params={"checkListId": check_list_id})

    @operation("CheckListsController_getCheckListStatus", "GET", "/check-lists/status",
               summary="Статус чек-листа по помещению")
    async def get_status(self, check_list_id: str, space_id: str) -> CheckListStatus:
        return await self._one("get_status", CheckListStatus,
                               params={"checkListId": check_list_id, "spaceId": space_id})

    @operation("CheckListsController_getCheckItemStatus", "GET", "/check-lists/item-status",
               summary="Статус категории чек-листа по помещению")
    async def get_item_status(self, check_item_id: str, space_id: str) -> CheckItemStatus:
        return await self._one("get_item_status", CheckItemStatus,
                               params={"checkItemId": check_item_id, "spaceId": space_id})

    @operation("CheckItemStatusesController_get", "GET", "/check-item-statuses",
               summary="Справочник статусов категорий чек-листа")
    async def item_statuses(self) -> builtins.list[DictItem]:
        return await self._many("item_statuses", DictItem)

    @operation("CheckListStatusesController_get", "GET", "/check-list-statuses",
               summary="Справочник статусов чек-листа")
    async def statuses(self) -> builtins.list[DictItem]:
        return await self._many("statuses", DictItem)


class ChecksResource(BaseResource):
    resource_name = "checks"

    @operation("ChecksController_getOne", "GET", "/checks/{id}", summary="Проверка по id")
    async def get(self, check_id: str) -> Check:
        return await self._one("get", Check, path_params={"id": check_id})
