"""Базовый класс ресурса: связывает методы с реестром операций и транспортом."""

from __future__ import annotations

from collections.abc import Mapping
from functools import cache
from typing import Any, ClassVar, TypeVar

from pydantic import BaseModel, TypeAdapter

from .._registry import Operation, collect
from .._transport import PreparedRequest, QueryValue, Transport
from ..errors import NotFoundError

M = TypeVar("M", bound=BaseModel)


@cache
def _list_adapter(model: type[BaseModel]) -> TypeAdapter[list[Any]]:
    return TypeAdapter(list[model])  # type: ignore[valid-type]


class BaseResource:
    resource_name: ClassVar[str] = ""
    operations: ClassVar[dict[str, Operation]] = {}

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if not cls.resource_name:
            raise TypeError(f"{cls.__name__}: не задан resource_name")
        cls.operations = collect(cls, cls.resource_name)

    def __init__(self, transport: Transport) -> None:
        self._transport = transport

    def _op(self, name: str) -> Operation:
        return self.operations[name]

    async def _raw(
        self,
        name: str,
        *,
        path_params: Mapping[str, Any] | None = None,
        params: Mapping[str, QueryValue] | None = None,
        json: Any = None,
    ) -> Any:
        return await self._transport.execute(self._op(name), path_params=path_params, params=params, json=json)

    def _prepare(
        self,
        name: str,
        *,
        path_params: Mapping[str, Any] | None = None,
        params: Mapping[str, QueryValue] | None = None,
        json: Any = None,
    ) -> PreparedRequest:
        return self._transport.prepare(self._op(name), path_params=path_params, params=params, json=json)

    async def _one(self, name: str, model: type[M], **kwargs: Any) -> M:
        return model.model_validate(await self._raw(name, **kwargs))

    async def _many(self, name: str, model: type[M], **kwargs: Any) -> list[M]:
        data = await self._raw(name, **kwargs)
        result: list[M] = _list_adapter(model).validate_python(data if data is not None else [])
        return result

    async def _many_or_empty(self, name: str, model: type[M], **kwargs: Any) -> list[M]:
        """Список; 404 («ничего не найдено») превращается в []."""
        try:
            return await self._many(name, model, **kwargs)
        except NotFoundError:
            return []

    async def _one_or_none(self, name: str, model: type[M], **kwargs: Any) -> M | None:
        """Объект; 404 превращается в None."""
        try:
            return await self._one(name, model, **kwargs)
        except NotFoundError:
            return None


def body(model: Any) -> Any:
    """Тело запроса из модели (camelCase, без None) или None."""
    return model.to_api() if model is not None else None


def warn_without_objects(objects: Any, where: str) -> None:
    if not objects:
        import warnings

        warnings.warn(
            f"{where}: запрос без фильтра по объекту может быть тяжёлым для сервера (502 после ~30 с). "
            "Укажите objects / object_id.",
            UserWarning,
            stacklevel=3,
        )
