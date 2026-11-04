"""Вывод фактической схемы из ответов, сверка со спецификацией и между снимками.

Схема хранит только структуру (поля и типы) — значения не сохраняются.
"""

from __future__ import annotations

from typing import Any


def _shape(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "str"
    if isinstance(value, list):
        return "list"
    if isinstance(value, dict):
        return "obj"
    return type(value).__name__


class Node:
    def __init__(self) -> None:
        self.n = 0
        self.dict_n = 0
        self.types: set[str] = set()
        self.fields: dict[str, Node] = {}
        self.items: Node | None = None

    def add(self, value: Any) -> None:
        self.n += 1
        self.types.add(_shape(value))
        if isinstance(value, dict):
            self.dict_n += 1
            for k, v in value.items():
                self.fields.setdefault(k, Node()).add(v)
        elif isinstance(value, list):
            for item in value:
                if self.items is None:
                    self.items = Node()
                self.items.add(item)

    def to_json(self) -> dict[str, Any]:
        out: dict[str, Any] = {"types": sorted(self.types)}
        if self.fields:
            out["fields"] = {k: v.to_json() for k, v in sorted(self.fields.items())}
        if self.items is not None:
            out["items"] = self.items.to_json()
        return out


def infer(values: list[Any]) -> Node:
    node = Node()
    for v in values:
        node.add(v)
    return node


# --- сверка со спецификацией ---------------------------------------------------------------------

_SPEC_TYPES = {
    "string": {"str"},
    "number": {"int", "float"},
    "integer": {"int"},
    "boolean": {"bool"},
    "object": {"obj"},
    "array": {"list"},
}


def _resolve(spec: dict[str, Any], schema: dict[str, Any] | None) -> dict[str, Any]:
    if not schema:
        return {}
    while True:
        if "$ref" in schema:
            ref = schema["$ref"].split("/")[-1]
            if not ref:
                return {}
            schema = spec["components"]["schemas"].get(ref, {})
        elif "allOf" in schema and len(schema["allOf"]) == 1:
            schema = schema["allOf"][0]
        else:
            return schema


def response_schema(spec: dict[str, Any], method: str, path: str) -> dict[str, Any] | None:
    op = spec.get("paths", {}).get(path, {}).get(method.lower())
    if not op:
        return None
    for code in ("200", "201"):
        resp = op.get("responses", {}).get(code)
        if resp:
            schema = resp.get("content", {}).get("application/json", {}).get("schema")
            return _resolve(spec, schema) if schema else None
    return None


def compare_with_spec(spec: dict[str, Any], fact: Node, schema: dict[str, Any] | None, path: str = "") -> list[str]:
    """Расхождения факта со спецификацией (информационно: спецификация не источник истины)."""
    if not schema:
        return []
    schema = _resolve(spec, schema)
    diffs: list[str] = []
    stype = schema.get("type")
    fact_types = fact.types - {"null"}
    if "properties" in schema and not stype:
        stype = "object"
    if stype in _SPEC_TYPES and fact_types and not fact_types <= _SPEC_TYPES[stype]:
        diffs.append(f"тип {path or '<ответ>'}: spec={stype}, факт={'|'.join(sorted(fact.types))}")
        return diffs
    if stype == "array" and fact.items is not None:
        diffs += compare_with_spec(spec, fact.items, schema.get("items"), f"{path}[]")
    if stype == "object" or "properties" in schema:
        props = schema.get("properties", {})
        required = set(schema.get("required", []))
        for name, child in fact.fields.items():
            sub = f"{path}.{name}" if path else name
            if name not in props:
                if props:
                    diffs.append(f"нет в spec: {sub}")
                continue
            diffs += compare_with_spec(spec, child, props[name], sub)
        for name in sorted(required):
            child = fact.fields.get(name)
            if fact.dict_n and (child is None or child.n < fact.dict_n):
                diffs.append(f"spec required, факт не всегда: {f'{path}.{name}' if path else name}")
    return diffs


# --- дрейф между снимками ------------------------------------------------------------------------


def _flatten(snapshot: dict[str, Any], prefix: str = "") -> dict[str, list[str]]:
    out = {prefix or "<ответ>": snapshot.get("types", [])}
    for name, child in snapshot.get("fields", {}).items():
        out.update(_flatten(child, f"{prefix}.{name}" if prefix else name))
    if "items" in snapshot:
        out.update(_flatten(snapshot["items"], f"{prefix}[]"))
    return out


def drift(old: dict[str, Any], new: dict[str, Any]) -> list[str]:
    a, b = _flatten(old), _flatten(new)
    diffs = [f"появилось поле: {k}" for k in sorted(set(b) - set(a))]
    diffs += [f"пропало поле: {k}" for k in sorted(set(a) - set(b))]
    diffs += [f"сменился тип {k}: {a[k]} → {b[k]}" for k in sorted(set(a) & set(b))
              if set(b[k]) - {"null"} and set(a[k]) - {"null"} and set(b[k]) - set(a[k]) - {"null"}]
    return diffs
