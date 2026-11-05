"""Список и дерево объектов компании.

В API нет метода «все объекты». fact (2026-11-05): объекты компании перечисляются в наборах видов работ
(`/categories-sets`), наборах меток (`/tags-sets`) и чек-листах (`/check-lists`); карточка каждого читается через
`/objects/{id}`, дерево строится по `parentId` (UUID). Объект без набора видов работ, без набора меток и без
чек-листа этим способом не найти.

`includeObjectsChildren` сервер игнорирует (fact), поэтому дочерние объекты подставляются явно через
`ObjectTree.descendants()`. Фильтры по объектам принимают только UUID — `ObjectTree.resolve()` переводит старый
24-hex id (`externalId` объекта) в UUID.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Iterable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..errors import ForbiddenError, NotFoundError
from ..models.objects import ConstructionObject

if TYPE_CHECKING:
    from ..client import TehzorClient

logger = logging.getLogger("tehzor")


class ObjectTree:
    def __init__(self, objects: Iterable[ConstructionObject]) -> None:
        self.nodes: dict[str, ConstructionObject] = {o.id: o for o in objects}
        self._by_external = {o.external_id: o.id for o in self.nodes.values() if o.external_id}
        self._children: dict[str, list[str]] = {}
        for o in self.nodes.values():
            parent = self.parent_of(o.id)
            if parent:
                self._children.setdefault(parent, []).append(o.id)
        for ids in self._children.values():
            ids.sort(key=lambda i: (self.nodes[i].name or "").strip())

    def __len__(self) -> int:
        return len(self.nodes)

    def __contains__(self, object_id: object) -> bool:
        return object_id in self.nodes

    def resolve(self, object_id: str) -> str | None:
        """UUID объекта по UUID или по старому id (externalId); None — объект неизвестен."""
        if object_id in self.nodes:
            return object_id
        return self._by_external.get(object_id)

    def parent_of(self, object_id: str) -> str | None:
        node = self.nodes.get(object_id)
        if node is None or not node.parent_id:
            return None
        return self.resolve(node.parent_id) or node.parent_id

    def children(self, object_id: str) -> list[str]:
        return list(self._children.get(object_id, []))

    def roots(self) -> list[str]:
        return sorted((i for i in self.nodes if self.parent_of(i) not in self.nodes),
                      key=lambda i: (self.nodes[i].name or "").strip())

    def descendants(self, object_ids: Iterable[str], *, include_self: bool = True) -> list[str]:
        """Объекты и все их дочерние (порядок сохраняется, без повторов)."""
        result: list[str] = []
        seen: set[str] = set()
        stack = [i for i in object_ids][::-1]
        first = set(stack)
        while stack:
            current = stack.pop()
            if current in seen:
                continue
            seen.add(current)
            if include_self or current not in first:
                result.append(current)
            stack.extend(reversed(self.children(current)))
        return result

    def path(self, object_id: str) -> list[str]:
        """Названия от корня до объекта: ЖК → корпус → секция."""
        names: list[str] = []
        current: str | None = object_id
        guard = 0
        while current and current in self.nodes and guard < 20:
            names.append((self.nodes[current].name or current).strip())
            current = self.parent_of(current)
            guard += 1
        return names[::-1]

    def ancestors(self, object_id: str) -> list[str]:
        """Родители от ближайшего к корню."""
        result: list[str] = []
        current = self.parent_of(object_id)
        while current and current in self.nodes and current not in result:
            result.append(current)
            current = self.parent_of(current)
        return result

    def name(self, object_id: str) -> str:
        node = self.nodes.get(object_id)
        return (node.name or object_id).strip() if node else object_id

    def as_tree(self, annotate: Any = None) -> list[dict[str, Any]]:
        def build(i: str) -> dict[str, Any]:
            o = self.nodes[i]
            item: dict[str, Any] = {"id": o.id, "name": (o.name or "").strip(), "stage": o.stage, "city": o.city,
                                    "external_id": o.external_id}
            if annotate is not None:
                item.update({k: v for k, v in annotate(i).items() if v})
            kids = [build(c) for c in self.children(i)]
            if kids:
                item["children"] = kids
            return item

        return [build(r) for r in self.roots()]


async def _collect_ids(client: TehzorClient) -> set[str]:
    sets, tags, check_lists = await asyncio.gather(client.categories.sets(), client.tags.sets(),
                                                   client.check_lists.list())
    ids: set[str] = set()
    for s in sets:
        ids.update(s.objects or [])
    for t in tags:
        ids.update(t.objects or [])
    for cl in check_lists:
        ids.update(o.id for o in (cl.objects or []))
    return ids


async def discover_objects(client: TehzorClient) -> ObjectTree:
    """Все объекты компании, доступные ключу, с деревом. Около 90 запросов (лимит частоты клиента)."""
    pending = await _collect_ids(client)
    found: dict[str, ConstructionObject] = {}
    checked: set[str] = set()
    while pending:
        batch = sorted(pending - checked)
        checked.update(batch)

        async def fetch(object_id: str) -> ConstructionObject | None:
            try:
                return await client.objects.get(object_id)
            except (NotFoundError, ForbiddenError):
                logger.info("tehzor: объект %s недоступен", object_id)
                return None

        for obj in await asyncio.gather(*(fetch(i) for i in batch)):
            if obj is not None:
                found[obj.id] = obj
        # родители, которых нет в источниках, дочитываются отдельно
        known = set(found) | {o.external_id for o in found.values() if o.external_id}
        pending = {o.parent_id for o in found.values() if o.parent_id and o.parent_id not in known} - checked
    return ObjectTree(found.values())


def snapshot_diff(tree: ObjectTree, path: Path) -> tuple[list[str], list[str]]:
    """Сравнить со снимком прошлого обхода и сохранить новый: (новые id, исчезнувшие id)."""
    previous: dict[str, str] = {}
    if path.exists():
        try:
            previous = json.loads(path.read_text(encoding="utf-8")).get("objects", {})
        except (OSError, ValueError):
            previous = {}
    current = {i: tree.name(i) for i in tree.nodes}
    new = sorted(set(current) - set(previous)) if previous else []
    removed = sorted(set(previous) - set(current)) if previous else []
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"objects": current}, ensure_ascii=False, indent=1), encoding="utf-8")
    except OSError as exc:
        logger.warning("tehzor: не удалось сохранить снимок объектов %s: %s", path, exc)
    return new, removed
