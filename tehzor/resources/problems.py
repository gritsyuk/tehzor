"""Нарушения (problems). Изменяющие методы — этап 4."""

from __future__ import annotations

import builtins
from collections.abc import AsyncIterator

from .._pagination import DEFAULT_PAGE_SIZE, iter_pages
from .._registry import operation
from ..models.common import DictItem
from ..models.problems import Problem, ProblemFilters, ProblemReply
from ._base import BaseResource, body, warn_without_objects


class ProblemsResource(BaseResource):
    resource_name = "problems"

    @operation("ProblemsController_getOne", "GET", "/problems/{id}", summary="Возвращает нарушение по id")
    async def get(self, problem_id: str) -> Problem:
        return await self._one("get", Problem, path_params={"id": problem_id})

    @operation("ProblemsController_getMany", "POST", "/problems/get-problems", paginated=True,
               summary="Возвращает страницу нарушений по фильтрам (укажите objects)")
    async def list(
        self,
        filters: ProblemFilters | None = None,
        *,
        limit: int = DEFAULT_PAGE_SIZE,
        offset: int = 0,
        user_id: str | None = None,
    ) -> builtins.list[Problem]:
        warn_without_objects(filters.objects if filters else None, "problems.list")
        return await self._many("list", Problem, params={"limit": limit, "offset": offset, "userId": user_id},
                                json=body(filters) or {})

    async def iter(
        self,
        filters: ProblemFilters | None = None,
        *,
        page_size: int = DEFAULT_PAGE_SIZE,
        max_items: int | None = None,
        user_id: str | None = None,
    ) -> AsyncIterator[Problem]:
        """Все нарушения по фильтрам, постранично."""
        async def fetch(limit: int, offset: int) -> builtins.list[Problem]:
            return await self.list(filters, limit=limit, offset=offset, user_id=user_id)

        async for item in iter_pages(fetch, page_size=page_size, max_items=max_items):
            yield item

    @operation("ProblemsController_getReply", "GET", "/problems/{id}/reply",
               summary="Последний официальный ответ по нарушению (None, если ответа нет)")
    async def reply(self, problem_id: str) -> ProblemReply | None:
        return await self._one_or_none("reply", ProblemReply, path_params={"id": problem_id})

    @operation("ProblemStatusesController_get", "GET", "/problem-statuses", summary="Справочник статусов нарушений")
    async def statuses(self) -> builtins.list[DictItem]:
        return await self._many("statuses", DictItem)
