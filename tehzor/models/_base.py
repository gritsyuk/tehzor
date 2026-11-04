"""Базовые классы моделей.

Модели ответов строятся по фактическим ответам API (контрактные тесты), а не по openapi.json:
обязателен только `id`, неизвестные поля сохраняются в `model_extra`, чтобы новые поля
на сервере не ломали разбор, а контрактные тесты могли их заметить.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class TehzorModel(BaseModel):
    """Модель ответа API."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="allow",
    )


class TehzorRequest(BaseModel):
    """Модель тела запроса: лишние поля запрещены, None не отправляется."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
    )

    def to_api(self) -> dict[str, Any]:
        return self.model_dump(by_alias=True, exclude_none=True, mode="json")


def iter_extras(value: Any, path: str = "") -> Iterator[tuple[str, Any]]:
    """Рекурсивно перечисляет поля ответа, не описанные в моделях: (путь, значение)."""
    if isinstance(value, BaseModel):
        for key, extra in (value.model_extra or {}).items():
            yield (f"{path}.{key}" if path else key), extra
        for name in type(value).model_fields:
            yield from iter_extras(getattr(value, name), f"{path}.{name}" if path else name)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from iter_extras(item, f"{path}[]")
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from iter_extras(item, f"{path}.{key}" if path else str(key))
