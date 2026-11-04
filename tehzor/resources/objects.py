"""Объекты (objects): объект, стадии, процессы."""

from __future__ import annotations

from .._registry import operation
from ..models.objects import ConstructionObject, HealthStatus, ProcessInfo, StageInfo
from ._base import BaseResource


class ObjectsResource(BaseResource):
    resource_name = "objects"

    @operation("ObjectsController_getOne", "GET", "/objects/{id}",
               summary="Возвращает объект по внутреннему (UUID) или внешнему id")
    async def get(self, object_id: str) -> ConstructionObject:
        return await self._one("get", ConstructionObject, path_params={"id": object_id})

    @operation("StagesController_get", "GET", "/stages", summary="Возвращает список стадий")
    async def stages(self) -> list[StageInfo]:
        return await self._many("stages", StageInfo)

    @operation("ProcessesController_get", "GET", "/processes", summary="Возвращает список процессов")
    async def processes(self) -> list[ProcessInfo]:
        return await self._many("processes", ProcessInfo)


class ServiceResource(BaseResource):
    """Служебные методы, не описанные в openapi.json."""

    resource_name = "service"

    @operation("observed:HealthReadiness", "GET", "/health/readiness", documented=False, mcp=False,
               summary="Проверка готовности API (не описан в официальной документации)")
    async def health(self) -> HealthStatus:
        return await self._one("health", HealthStatus)
