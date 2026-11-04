"""Реестр операций API.

Каждый публичный метод ресурса помечается декоратором `@operation(...)`. Реестр — единый
источник для трёх потребителей:

* теста полноты (все операции из openapi.json реализованы),
* MCP-сервера (инструменты генерируются из реестра),
* контрактных тестов (только операции `kind == "R"` могут ходить в живое API).

Ключ операции — пара (HTTP-метод, шаблон пути из спецификации): один operationId в openapi.json
может встречаться на нескольких путях.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field, replace
from typing import Any, Literal, TypeVar

Kind = Literal["R", "W", "D"]
"""R — чтение, W — запись (создание/изменение), D — удаление."""

F = TypeVar("F", bound=Callable[..., Any])

_ATTR = "__tehzor_operation__"


@dataclass(frozen=True)
class Operation:
    operation_id: str
    method: str
    path: str
    kind: Kind
    summary: str = ""
    idempotent: bool = True
    """Можно ли безопасно повторить запрос. Создание (create*) — нет: повтор даст дубль."""
    documented: bool = True
    """False — метода нет в openapi.json, он найден на живом API."""
    paginated: bool = False
    mcp: bool = True
    """Публиковать ли операцию как MCP-инструмент."""
    resource: str = ""
    name: str = ""
    tags: tuple[str, ...] = field(default=())

    @property
    def key(self) -> tuple[str, str]:
        return (self.method, self.path)

    @property
    def tool_name(self) -> str:
        return f"{self.resource}_{self.name}"

    @property
    def mutating(self) -> bool:
        return self.kind != "R"


def operation(
    operation_id: str,
    method: str,
    path: str,
    *,
    kind: Kind = "R",
    summary: str = "",
    idempotent: bool | None = None,
    documented: bool = True,
    paginated: bool = False,
    mcp: bool = True,
) -> Callable[[F], F]:
    """Помечает метод ресурса как операцию API.

    `idempotent` по умолчанию True для чтения и False для записи/удаления: запись повторяется
    только если это явно разрешено (изменение по id, смена статуса).
    """
    if idempotent is None:
        idempotent = kind == "R"
    op = Operation(
        operation_id=operation_id,
        method=method.upper(),
        path=path,
        kind=kind,
        summary=summary,
        idempotent=idempotent,
        documented=documented,
        paginated=paginated,
        mcp=mcp,
    )

    def decorator(func: F) -> F:
        setattr(func, _ATTR, op)
        return func

    return decorator


class Registry:
    def __init__(self) -> None:
        self._by_key: dict[tuple[str, str], Operation] = {}
        self._by_tool: dict[str, Operation] = {}

    def add(self, op: Operation) -> None:
        existing = self._by_key.get(op.key)
        if existing is not None and existing.tool_name != op.tool_name:
            raise ValueError(f"Операция {op.method} {op.path} уже зарегистрирована как {existing.tool_name}")
        self._by_key[op.key] = op
        self._by_tool[op.tool_name] = op

    def all(self) -> list[Operation]:
        return sorted(self._by_key.values(), key=lambda o: o.tool_name)

    def get(self, method: str, path: str) -> Operation | None:
        return self._by_key.get((method.upper(), path))

    def by_tool(self, tool_name: str) -> Operation:
        return self._by_tool[tool_name]

    def __len__(self) -> int:
        return len(self._by_key)


REGISTRY = Registry()


def collect(cls: type, resource_name: str) -> dict[str, Operation]:
    """Собирает операции класса ресурса и регистрирует их в REGISTRY."""
    found: dict[str, Operation] = {}
    for attr, value in vars(cls).items():
        op = getattr(value, _ATTR, None)
        if isinstance(op, Operation):
            bound = replace(op, resource=resource_name, name=attr)
            REGISTRY.add(bound)
            found[attr] = bound
    return found
