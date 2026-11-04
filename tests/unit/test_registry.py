"""Реестр операций и сверка с заявленной спецификацией docs/openapi.json.

openapi.json — каталог заявленных методов (не источник истины по формату ответов):
по нему проверяется только то, что ни один заявленный метод не пропущен.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import tehzor  # noqa: F401  — регистрирует ресурсы
from tehzor._registry import REGISTRY, Operation, Registry

SPEC = json.loads((Path(__file__).parents[2] / "docs" / "openapi.json").read_text(encoding="utf-8"))
SPEC_OPS = {(m.upper(), p): o.get("operationId") for p, v in SPEC["paths"].items() for m, o in v.items()}


def test_spec_is_declared_catalog() -> None:
    assert SPEC["info"]["version"]
    assert len(SPEC_OPS) == 73


def test_documented_operations_exist_in_spec() -> None:
    for op in REGISTRY.all():
        if op.documented:
            assert op.key in SPEC_OPS, f"{op.tool_name}: {op.method} {op.path} нет в openapi.json"
            assert SPEC_OPS[op.key] == op.operation_id, f"{op.tool_name}: другой operationId"


def test_undocumented_operations_absent_from_spec() -> None:
    for op in REGISTRY.all():
        if not op.documented:
            assert op.key not in SPEC_OPS, f"{op.tool_name} описан в openapi.json — снимите documented=False"


def test_spec_kinds_match_http_semantics() -> None:
    for op in REGISTRY.all():
        if op.method == "DELETE":
            assert op.kind == "D"
        if op.method == "GET":
            assert op.kind == "R"


@pytest.mark.xfail(reason="этап 4: реализованы не все 73 операции", strict=False)
def test_all_declared_operations_implemented() -> None:
    implemented = {op.key for op in REGISTRY.all() if op.documented}
    missing = sorted(set(SPEC_OPS) - implemented)
    assert not missing, f"Не реализовано {len(missing)} из {len(SPEC_OPS)}: {missing[:5]}…"


def test_tool_names_and_defaults() -> None:
    op = REGISTRY.by_tool("objects_get")
    assert (op.method, op.path, op.kind, op.idempotent) == ("GET", "/objects/{id}", "R", True)
    health = REGISTRY.by_tool("service_health")
    assert not health.documented and not health.mcp


def test_write_is_not_idempotent_by_default() -> None:
    from tehzor._registry import operation

    @operation("X_create", "POST", "/x", kind="W")
    async def create() -> None: ...

    assert create.__tehzor_operation__.idempotent is False  # type: ignore[attr-defined]


def test_registry_rejects_conflicting_key() -> None:
    reg = Registry()
    reg.add(Operation("A", "GET", "/a", "R", resource="r", name="one"))
    with pytest.raises(ValueError):
        reg.add(Operation("A", "GET", "/a", "R", resource="r", name="two"))
