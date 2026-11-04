"""Собственники помещений (space-owners). Только изменяющие операции: проверяются на заглушках."""

from __future__ import annotations

from typing import Any, Literal, overload

from .._registry import operation
from .._transport import PreparedRequest
from ..models.space_owners import SpaceOwner, SpaceOwnerCreate, SpaceOwnerEdit, SpaceOwnerGetOrCreate
from ._base import BaseResource


class SpaceOwnersResource(BaseResource):
    resource_name = "space_owners"

    @overload
    async def create(self, data: SpaceOwnerCreate, *, dry_run: Literal[False] = False) -> SpaceOwner: ...

    @overload
    async def create(self, data: SpaceOwnerCreate, *, dry_run: Literal[True]) -> PreparedRequest: ...

    @operation(
        "SpaceOwnersController_addSpaceOwner",
        "POST",
        "/space-owners",
        kind="W",
        idempotent=False,
        summary="Добавляет собственника помещений",
    )
    async def create(self, data: SpaceOwnerCreate, *, dry_run: bool = False) -> SpaceOwner | PreparedRequest:
        return await self._write("create", SpaceOwner, dry_run=dry_run, json=data.to_api())

    @overload
    async def get_or_create(self, data: SpaceOwnerGetOrCreate, *, dry_run: Literal[False] = False) -> SpaceOwner: ...

    @overload
    async def get_or_create(self, data: SpaceOwnerGetOrCreate, *, dry_run: Literal[True]) -> PreparedRequest: ...

    @operation(
        "SpaceOwnersController_getOrCreateSpaceOwner",
        "POST",
        "/space-owners/get-or-create",
        kind="W",
        idempotent=False,
        summary="Возвращает существующего собственника или создаёт нового",
    )
    async def get_or_create(
        self, data: SpaceOwnerGetOrCreate, *, dry_run: bool = False
    ) -> SpaceOwner | PreparedRequest:
        return await self._write("get_or_create", SpaceOwner, dry_run=dry_run, json=data.to_api())

    @overload
    async def edit(self, owner_id: str, data: SpaceOwnerEdit, *, dry_run: Literal[False] = False) -> SpaceOwner: ...

    @overload
    async def edit(self, owner_id: str, data: SpaceOwnerEdit, *, dry_run: Literal[True]) -> PreparedRequest: ...

    @operation(
        "SpaceOwnersController_editSpaceOwner",
        "POST",
        "/space-owners/{id}",
        kind="W",
        idempotent=True,
        summary="Изменяет данные собственника",
    )
    async def edit(self, owner_id: str, data: SpaceOwnerEdit, *, dry_run: bool = False) -> SpaceOwner | PreparedRequest:
        return await self._write("edit", SpaceOwner, dry_run=dry_run, path_params={"id": owner_id}, json=data.to_api())

    @overload
    async def delete(self, owner_id: str, *, dry_run: Literal[False] = False) -> Any: ...

    @overload
    async def delete(self, owner_id: str, *, dry_run: Literal[True]) -> PreparedRequest: ...

    @operation(
        "SpaceOwnersController_deleteSpaceOwner",
        "DELETE",
        "/space-owners/{ownerId}/delete",
        kind="D",
        idempotent=False,
        summary="Удаляет собственника помещения (необратимо)",
    )
    async def delete(self, owner_id: str, *, dry_run: bool = False) -> Any | PreparedRequest:
        return await self._write("delete", None, dry_run=dry_run, path_params={"ownerId": owner_id})

    @overload
    async def bind(
        self, owner_id: str, space_id: str, *, unbind_existing_owners: bool = False, dry_run: Literal[False] = False
    ) -> SpaceOwner: ...

    @overload
    async def bind(
        self, owner_id: str, space_id: str, *, unbind_existing_owners: bool = False, dry_run: Literal[True]
    ) -> PreparedRequest: ...

    @operation(
        "SpaceOwnersController_bindSpaceOwner",
        "POST",
        "/space-owners/{ownerId}/bind/{spaceId}",
        kind="W",
        idempotent=True,
        summary="Привязывает собственника к помещению",
    )
    async def bind(
        self, owner_id: str, space_id: str, *, unbind_existing_owners: bool = False, dry_run: bool = False
    ) -> SpaceOwner | PreparedRequest:
        return await self._write(
            "bind",
            SpaceOwner,
            dry_run=dry_run,
            path_params={"ownerId": owner_id, "spaceId": space_id},
            json={"unbindExistingOwners": unbind_existing_owners},
        )

    @overload
    async def unbind(self, owner_id: str, space_id: str, *, dry_run: Literal[False] = False) -> SpaceOwner: ...

    @overload
    async def unbind(self, owner_id: str, space_id: str, *, dry_run: Literal[True]) -> PreparedRequest: ...

    @operation(
        "SpaceOwnersController_unbindSpaceOwner",
        "POST",
        "/space-owners/{ownerId}/unbind/{spaceId}",
        kind="W",
        idempotent=True,
        summary="Отвязывает собственника от помещения",
    )
    async def unbind(self, owner_id: str, space_id: str, *, dry_run: bool = False) -> SpaceOwner | PreparedRequest:
        return await self._write(
            "unbind", SpaceOwner, dry_run=dry_run, path_params={"ownerId": owner_id, "spaceId": space_id}
        )
