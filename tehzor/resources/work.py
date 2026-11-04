"""Приёмки работ, внутренние приёмки, передачи собственникам, гарантия, задачи, комментарии.

Изменяющие методы проверяются только на заглушках.
"""

from __future__ import annotations

import builtins
from collections.abc import AsyncIterator, Sequence
from typing import Literal, overload

from .._pagination import DEFAULT_PAGE_SIZE, iter_pages
from .._registry import operation
from .._transport import PreparedRequest
from ..enums import OwnerAcceptanceResolution, OwnerAcceptanceStatus, ProblemField
from ..models.acceptances import InternalAcceptance, InternalAcceptanceCreate, OwnerAcceptance, OwnerAcceptanceCreate
from ..models.comments import Comment, CommentCreate, CommentFilters
from ..models.common import DictItem
from ..models.problems import Problem
from ..models.tasks import Task, TaskCreate, TaskEdit, TaskFilters
from ..models.warranty_claims import WarrantyClaim, WarrantyClaimCreate
from ..models.work_acceptances import (
    WorkAcceptance,
    WorkAcceptanceCreate,
    WorkAcceptanceCreateResult,
    WorkAcceptanceEdit,
    WorkAcceptanceFilters,
)
from ._base import BaseResource, body, warn_without_objects


class WorkAcceptancesResource(BaseResource):
    resource_name = "work_acceptances"

    @overload
    async def edit(
        self, work_acceptance_id: str, data: WorkAcceptanceEdit, *, dry_run: Literal[False] = False
    ) -> WorkAcceptance: ...

    @overload
    async def edit(
        self, work_acceptance_id: str, data: WorkAcceptanceEdit, *, dry_run: Literal[True]
    ) -> PreparedRequest: ...

    @operation(
        "WorkAcceptancesController_edit",
        "POST",
        "/work-acceptances/{id}",
        kind="W",
        idempotent=True,
        summary="Изменяет приёмку работ",
    )
    async def edit(
        self, work_acceptance_id: str, data: WorkAcceptanceEdit, *, dry_run: bool = False
    ) -> WorkAcceptance | PreparedRequest:
        return await self._write(
            "edit", WorkAcceptance, dry_run=dry_run, path_params={"id": work_acceptance_id}, json=data.to_api()
        )

    @overload
    async def create_many(
        self, items: Sequence[WorkAcceptanceCreate], *, dry_run: Literal[False] = False
    ) -> builtins.list[WorkAcceptanceCreateResult]: ...

    @overload
    async def create_many(
        self, items: Sequence[WorkAcceptanceCreate], *, dry_run: Literal[True]
    ) -> PreparedRequest: ...

    @operation(
        "WorkAcceptancesController_addMany",
        "POST",
        "/work-acceptances",
        kind="W",
        idempotent=False,
        summary="Создаёт приёмки работ пачкой; ошибки по элементам — в результате (error, error_description)",
    )
    async def create_many(
        self, items: Sequence[WorkAcceptanceCreate], *, dry_run: bool = False
    ) -> builtins.list[WorkAcceptanceCreateResult] | PreparedRequest:
        result = await self._write("create_many", None, dry_run=dry_run, json=[x.to_api() for x in items])
        if dry_run:
            return result
        return [WorkAcceptanceCreateResult.model_validate(x) for x in (result or [])]

    @operation("WorkAcceptancesController_getById", "GET", "/work-acceptances/{id}", summary="Приёмка работ по id")
    async def get(self, work_acceptance_id: str) -> WorkAcceptance:
        return await self._one("get", WorkAcceptance, path_params={"id": work_acceptance_id})

    @operation(
        "WorkAcceptancesController_getMany",
        "POST",
        "/work-acceptances/get-work-acceptances",
        paginated=True,
        summary="Страница приёмок работ объекта",
    )
    async def list(
        self,
        object_id: str | None = None,
        filters: WorkAcceptanceFilters | None = None,
        *,
        limit: int = DEFAULT_PAGE_SIZE,
        offset: int = 0,
    ) -> builtins.list[WorkAcceptance]:
        warn_without_objects(object_id or (filters.work_acceptance_ids if filters else None), "work_acceptances.list")
        return await self._many(
            "list",
            WorkAcceptance,
            params={"limit": limit, "offset": offset, "objectId": object_id},
            json=body(filters) or {},
        )

    async def iter(
        self,
        object_id: str | None = None,
        filters: WorkAcceptanceFilters | None = None,
        *,
        page_size: int = DEFAULT_PAGE_SIZE,
        max_items: int | None = None,
    ) -> AsyncIterator[WorkAcceptance]:
        async def fetch(limit: int, offset: int) -> builtins.list[WorkAcceptance]:
            return await self.list(object_id, filters, limit=limit, offset=offset)

        async for item in iter_pages(fetch, page_size=page_size, max_items=max_items):
            yield item

    @operation(
        "WorkAcceptanceStatusesController_get",
        "GET",
        "/work-acceptance-statuses",
        summary="Справочник статусов приёмок работ",
    )
    async def statuses(self) -> builtins.list[DictItem]:
        return await self._many("statuses", DictItem)

    @operation(
        "WorkAcceptanceFrontTypesController_get",
        "GET",
        "/work-acceptance-front-types",
        summary="Справочник типов фронта приёмок работ",
    )
    async def front_types(self) -> builtins.list[DictItem]:
        return await self._many("front_types", DictItem)

    @operation(
        "WorkAcceptanceTypesController_get", "GET", "/work-acceptance-types", summary="Справочник типов приёмок работ"
    )
    async def types(self) -> builtins.list[DictItem]:
        return await self._many("types", DictItem)


class InternalAcceptancesResource(BaseResource):
    resource_name = "internal_acceptances"

    @overload
    async def create(
        self, data: InternalAcceptanceCreate, *, dry_run: Literal[False] = False
    ) -> InternalAcceptance: ...

    @overload
    async def create(self, data: InternalAcceptanceCreate, *, dry_run: Literal[True]) -> PreparedRequest: ...

    @operation(
        "InternalAcceptancesController_createInternalAcceptance",
        "POST",
        "/internal-acceptances",
        kind="W",
        idempotent=False,
        summary="Создаёт внутреннюю приёмку",
    )
    async def create(
        self, data: InternalAcceptanceCreate, *, dry_run: bool = False
    ) -> InternalAcceptance | PreparedRequest:
        return await self._write("create", InternalAcceptance, dry_run=dry_run, json=data.to_api())

    @operation(
        "InternalAcceptancesController_getMany",
        "POST",
        "/internal-acceptances/get-internal-acceptances",
        paginated=True,
        summary="Страница внутренних приёмок объекта",
    )
    async def list(
        self, object_id: str | None = None, *, limit: int = DEFAULT_PAGE_SIZE, offset: int = 0
    ) -> builtins.list[InternalAcceptance]:
        warn_without_objects(object_id, "internal_acceptances.list")
        return await self._many(
            "list", InternalAcceptance, params={"objectId": object_id, "limit": limit, "offset": offset}
        )

    async def iter(
        self, object_id: str | None = None, *, page_size: int = DEFAULT_PAGE_SIZE, max_items: int | None = None
    ) -> AsyncIterator[InternalAcceptance]:
        async def fetch(limit: int, offset: int) -> builtins.list[InternalAcceptance]:
            return await self.list(object_id, limit=limit, offset=offset)

        async for item in iter_pages(fetch, page_size=page_size, max_items=max_items):
            yield item

    @operation(
        "InternalAcceptancesController_getOne", "GET", "/internal-acceptances/{id}", summary="Внутренняя приёмка по id"
    )
    async def get(self, internal_acceptance_id: str) -> InternalAcceptance:
        return await self._one("get", InternalAcceptance, path_params={"id": internal_acceptance_id})

    @operation(
        "ProblemsController_getProblems",
        "GET",
        "/internal-acceptances/{internalAcceptanceId}/problems",
        summary="Нарушения внутренней приёмки",
    )
    async def problems(self, internal_acceptance_id: str) -> builtins.list[Problem]:
        return await self._many("problems", Problem, path_params={"internalAcceptanceId": internal_acceptance_id})


class OwnerAcceptancesResource(BaseResource):
    resource_name = "owner_acceptances"

    @overload
    async def create(self, data: OwnerAcceptanceCreate, *, dry_run: Literal[False] = False) -> str: ...

    @overload
    async def create(self, data: OwnerAcceptanceCreate, *, dry_run: Literal[True]) -> PreparedRequest: ...

    @operation(
        "OwnerAcceptancesController_create",
        "POST",
        "/owner-acceptances",
        kind="W",
        idempotent=False,
        summary="Создаёт передачу собственнику; возвращает её id",
    )
    async def create(self, data: OwnerAcceptanceCreate, *, dry_run: bool = False) -> str | PreparedRequest:
        result = await self._write("create", None, dry_run=dry_run, json=data.to_api())
        return result if dry_run else str(result)

    @overload
    async def set_status(
        self, owner_acceptance_id: str, status: OwnerAcceptanceStatus, *, dry_run: Literal[False] = False
    ) -> OwnerAcceptance: ...

    @overload
    async def set_status(
        self, owner_acceptance_id: str, status: OwnerAcceptanceStatus, *, dry_run: Literal[True]
    ) -> PreparedRequest: ...

    @operation(
        "OwnerAcceptancesController_editOwnerAcceptanceStatus",
        "POST",
        "/owner-acceptances/{ownerAcceptanceId}/edit-status/{ownerAcceptanceStatusId}",
        kind="W",
        idempotent=True,
        summary="Меняет статус передачи собственнику",
    )
    async def set_status(
        self, owner_acceptance_id: str, status: OwnerAcceptanceStatus, *, dry_run: bool = False
    ) -> OwnerAcceptance | PreparedRequest:
        return await self._write(
            "set_status",
            OwnerAcceptance,
            dry_run=dry_run,
            path_params={"ownerAcceptanceId": owner_acceptance_id, "ownerAcceptanceStatusId": status},
        )

    @overload
    async def set_resolution(
        self, owner_acceptance_id: str, resolution: OwnerAcceptanceResolution, *, dry_run: Literal[False] = False
    ) -> OwnerAcceptance: ...

    @overload
    async def set_resolution(
        self, owner_acceptance_id: str, resolution: OwnerAcceptanceResolution, *, dry_run: Literal[True]
    ) -> PreparedRequest: ...

    @operation(
        "OwnerAcceptancesController_editOwnerAcceptanceResolution",
        "POST",
        "/owner-acceptances/{ownerAcceptanceId}/edit-resolutions/{ownerAcceptanceResolutionsId}",
        kind="W",
        idempotent=True,
        summary="Меняет решение по передаче собственнику",
    )
    async def set_resolution(
        self, owner_acceptance_id: str, resolution: OwnerAcceptanceResolution, *, dry_run: bool = False
    ) -> OwnerAcceptance | PreparedRequest:
        return await self._write(
            "set_resolution",
            OwnerAcceptance,
            dry_run=dry_run,
            path_params={"ownerAcceptanceId": owner_acceptance_id, "ownerAcceptanceResolutionsId": resolution},
        )

    @operation(
        "OwnerAcceptancesController_getById", "GET", "/owner-acceptances/{id}", summary="Передача собственнику по id"
    )
    async def get(self, owner_acceptance_id: str) -> OwnerAcceptance:
        return await self._one("get", OwnerAcceptance, path_params={"id": owner_acceptance_id})

    @operation(
        "OwnerAcceptanceResolutionsController_get",
        "GET",
        "/owner-acceptance-resolutions",
        summary="Справочник решений собственников",
    )
    async def resolutions(self) -> builtins.list[DictItem]:
        return await self._many("resolutions", DictItem)

    @operation(
        "OwnerAcceptanceStatusesController_get",
        "GET",
        "/owner-acceptance-statuses",
        summary="Справочник статусов передач собственникам",
    )
    async def statuses(self) -> builtins.list[DictItem]:
        return await self._many("statuses", DictItem)


class WarrantyClaimsResource(BaseResource):
    resource_name = "warranty_claims"

    @overload
    async def create(self, data: WarrantyClaimCreate, *, dry_run: Literal[False] = False) -> WarrantyClaim: ...

    @overload
    async def create(self, data: WarrantyClaimCreate, *, dry_run: Literal[True]) -> PreparedRequest: ...

    @operation(
        "WarrantyClaimsController_create",
        "POST",
        "/warranty-claims",
        kind="W",
        idempotent=False,
        summary="Создаёт гарантийное заявление",
    )
    async def create(self, data: WarrantyClaimCreate, *, dry_run: bool = False) -> WarrantyClaim | PreparedRequest:
        return await self._write("create", WarrantyClaim, dry_run=dry_run, json=data.to_api())

    @operation(
        "WarrantyClaimsController_getById", "GET", "/warranty-claims/{id}", summary="Гарантийное заявление по id"
    )
    async def get(self, warranty_claim_id: str) -> WarrantyClaim:
        return await self._one("get", WarrantyClaim, path_params={"id": warranty_claim_id})

    @operation(
        "ProblemsController_getProblems",
        "GET",
        "/warranty-claims/{warrantyClaimId}/problems",
        summary="Нарушения гарантийного обращения",
    )
    async def problems(
        self, warranty_claim_id: str, fields: Sequence[ProblemField | str] | None = None
    ) -> builtins.list[Problem]:
        return await self._many(
            "problems",
            Problem,
            path_params={"warrantyClaimId": warranty_claim_id},
            params={"fields": list(fields) if fields else None},
        )

    @operation(
        "WarrantyClaimStatusesController_get",
        "GET",
        "/warranty-claim-statuses",
        summary="Справочник статусов гарантийных заявлений",
    )
    async def statuses(self) -> builtins.list[DictItem]:
        return await self._many("statuses", DictItem)


class TasksResource(BaseResource):
    resource_name = "tasks"

    @overload
    async def create(self, data: TaskCreate, *, dry_run: Literal[False] = False) -> Task: ...

    @overload
    async def create(self, data: TaskCreate, *, dry_run: Literal[True]) -> PreparedRequest: ...

    @operation("TasksController_create", "POST", "/tasks", kind="W", idempotent=False, summary="Создаёт задачу")
    async def create(self, data: TaskCreate, *, dry_run: bool = False) -> Task | PreparedRequest:
        return await self._write("create", Task, dry_run=dry_run, json=data.to_api())

    @overload
    async def edit(self, task_id: str, data: TaskEdit, *, dry_run: Literal[False] = False) -> Task: ...

    @overload
    async def edit(self, task_id: str, data: TaskEdit, *, dry_run: Literal[True]) -> PreparedRequest: ...

    @operation("TasksController_edit", "POST", "/tasks/{id}", kind="W", idempotent=True, summary="Изменяет задачу")
    async def edit(self, task_id: str, data: TaskEdit, *, dry_run: bool = False) -> Task | PreparedRequest:
        return await self._write("edit", Task, dry_run=dry_run, path_params={"id": task_id}, json=data.to_api())

    @operation(
        "TasksController_getMany",
        "POST",
        "/tasks/get-tasks",
        paginated=True,
        summary="Страница задач по фильтрам (укажите objects)",
    )
    async def list(
        self, filters: TaskFilters | None = None, *, limit: int = DEFAULT_PAGE_SIZE, offset: int = 0
    ) -> builtins.list[Task]:
        warn_without_objects(filters.objects if filters else None, "tasks.list")
        return await self._many("list", Task, params={"limit": limit, "offset": offset}, json=body(filters) or {})

    async def iter(
        self, filters: TaskFilters | None = None, *, page_size: int = DEFAULT_PAGE_SIZE, max_items: int | None = None
    ) -> AsyncIterator[Task]:
        async def fetch(limit: int, offset: int) -> builtins.list[Task]:
            return await self.list(filters, limit=limit, offset=offset)

        async for item in iter_pages(fetch, page_size=page_size, max_items=max_items):
            yield item

    @operation("TasksController_getOne", "GET", "/tasks/{id}", summary="Задача по id")
    async def get(self, task_id: str) -> Task:
        return await self._one("get", Task, path_params={"id": task_id})

    @operation("TaskTypesController_get", "GET", "/task-types", summary="Справочник типов задач")
    async def types(self) -> builtins.list[DictItem]:
        return await self._many("types", DictItem)

    @operation("TaskStatusesController_get", "GET", "/task-statuses", summary="Справочник статусов задач")
    async def statuses(self) -> builtins.list[DictItem]:
        return await self._many("statuses", DictItem)


class CommentsResource(BaseResource):
    resource_name = "comments"

    @overload
    async def create(self, data: CommentCreate, *, dry_run: Literal[False] = False) -> Comment: ...

    @overload
    async def create(self, data: CommentCreate, *, dry_run: Literal[True]) -> PreparedRequest: ...

    @operation(
        "CommentsController_create",
        "POST",
        "/comments",
        kind="W",
        idempotent=False,
        summary="Создаёт комментарий или официальный ответ",
    )
    async def create(self, data: CommentCreate, *, dry_run: bool = False) -> Comment | PreparedRequest:
        return await self._write("create", Comment, dry_run=dry_run, json=data.to_api())

    @operation("CommentsController_getOne", "GET", "/comments/{id}", summary="Комментарий по id")
    async def get(self, comment_id: str) -> Comment:
        return await self._one("get", Comment, path_params={"id": comment_id})

    @operation(
        "CommentsController_getMany",
        "POST",
        "/comments/get-comments",
        paginated=True,
        summary="Комментарии и официальные ответы по нарушению или приёмке работ",
    )
    async def list(
        self, filters: CommentFilters | None = None, *, limit: int = DEFAULT_PAGE_SIZE, offset: int = 0
    ) -> builtins.list[Comment]:
        warn_without_objects(filters.problem_id or filters.work_acceptance_id if filters else None, "comments.list")
        return await self._many("list", Comment, params={"limit": limit, "offset": offset}, json=body(filters) or {})

    async def iter(
        self, filters: CommentFilters | None = None, *, page_size: int = DEFAULT_PAGE_SIZE, max_items: int | None = None
    ) -> AsyncIterator[Comment]:
        async def fetch(limit: int, offset: int) -> builtins.list[Comment]:
            return await self.list(filters, limit=limit, offset=offset)

        async for item in iter_pages(fetch, page_size=page_size, max_items=max_items):
            yield item
