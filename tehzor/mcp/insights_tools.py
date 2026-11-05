"""Аналитические инструменты MCP поверх существующего API (только чтение).

objects_discover, problems_search, problems_summary, work_acceptances_search, projects_list, project_resolve,
ресурс tehzor://objects-tree. Правила расчёта и ограничения — в tehzor/insights/*.
"""

from __future__ import annotations

import asyncio
import re
import time
from collections.abc import Callable
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations

from ..insights import ObjectTree, discover_objects, snapshot_diff, summarize_problems
from ..insights.summary import DIMENSIONS, FETCH_STATUSES
from ..models.problems import Problem, ProblemFilters
from ..models.work_acceptances import WorkAcceptance, WorkAcceptanceFilters

if TYPE_CHECKING:
    from .server import State

_UUID = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
RO = ToolAnnotations(readOnlyHint=True, openWorldHint=True)


def _ann(title: str) -> ToolAnnotations:
    return ToolAnnotations(title=title, readOnlyHint=True, openWorldHint=True)


async def get_tree(state: State, refresh: bool = False) -> ObjectTree:
    """Дерево объектов из живого API (кэш на cache_ttl). Снимок для «новых объектов» обновляется при обходе."""
    async with state.tree_lock:
        fresh = state.tree is not None and time.monotonic() - state.tree_at < state.settings.cache_ttl
        if refresh or not fresh:
            tree = await discover_objects(state.require_client())
            state.tree_diff = snapshot_diff(tree, state.settings.state_dir / "objects.json")
            state.tree, state.tree_at = tree, time.monotonic()
        assert state.tree is not None
        return state.tree


async def resolve_scope(
    state: State, objects: list[str] | None, project: str | None, include_children: bool
) -> tuple[list[str], ObjectTree | None]:
    """UUID объектов запроса: из objects и/или кода проекта; старые id → UUID; при include_children — с дочерними."""
    ids: list[str] = []
    if project:
        if not state.projects.configured:
            raise ToolError("соответствия проектов не заданы (TEHZOR_MCP_PROJECTS) — передайте objects (UUID)")
        found = state.projects.find(project)
        if not found:
            raise ToolError(f"проект {project!r} не найден — список: projects_list")
        if len(found) > 1:
            raise ToolError(f"под {project!r} подходит несколько проектов: {', '.join(p.code for p in found[:10])}")
        if not found[0].objects:
            raise ToolError(f"у проекта {found[0].code} не указаны объекты Техзора")
        ids.extend(found[0].objects)
    ids.extend(objects or [])
    if not ids:
        raise ToolError("укажите objects (UUID объектов) или project (код проекта)")
    tree = state.tree
    if include_children or any(not _UUID.match(i) for i in ids) or (tree is None and include_children):
        tree = await get_tree(state)
    resolved: list[str] = []
    for raw in ids:
        r = tree.resolve(raw) if tree is not None else None
        if r is None:
            if not _UUID.match(raw):
                raise ToolError(
                    f"объект {raw!r} не найден: фильтры принимают только UUID объекта, старый id "
                    "переводится по дереву объектов — обновите objects_discover(refresh=true)"
                )
            r = raw
        resolved.append(r)
    if include_children and tree is not None:
        resolved = tree.descendants(resolved)
    return list(dict.fromkeys(resolved)), tree


def _name(tree: ObjectTree | None, object_id: str | None, fallback: str | None = None) -> str | None:
    if object_id and tree is not None and object_id in tree:
        return " / ".join(tree.path(object_id))
    return fallback or object_id


def _compact_problem(p: Problem, tree: ObjectTree | None) -> dict[str, Any]:
    return {
        "id": p.id,
        "number": p.number,
        "object": _name(tree, p.object.id if p.object else None, p.object.name if p.object else None),
        "status": p.status.name if p.status else None,
        "status_id": p.status.id if p.status else None,
        "stage": p.stage,
        "category": p.category.name if p.category else None,
        "space": p.space.name if p.space else None,
        "space_id": p.space.id if p.space else None,
        "planned_fix_date": p.planned_fix_date.isoformat() if p.planned_fix_date else None,
        "critical": p.critical,
        "description": (p.description or "")[:200] or None,
    }


def register_insights(
    mcp: FastMCP,
    state: State,
    dumps: Callable[[Any], str],
    tool_error: Callable[[Exception], ToolError],
) -> None:
    s = state.settings

    @mcp.tool(
        name="objects_discover",
        description="Все объекты компании деревом (ЖК → корпус → секция) с id, стадией и кодом проекта. API не "
        "отдаёт список объектов: он собирается из наборов видов работ, наборов меток и чек-листов (около 20 с, "
        "затем кэш на час). new_since_last / removed_since_last — изменения с прошлого обхода. refresh=true — "
        "обойти заново. Объект без наборов и чек-листов не будет найден.",
        annotations=_ann("Объекты компании"),
        structured_output=False,
    )
    async def objects_discover(refresh: bool = False, flat: bool = False) -> str:
        try:
            tree = await get_tree(state, refresh)
        except Exception as exc:
            raise tool_error(exc) from exc

        def annotate(oid: str) -> dict[str, Any]:
            p = next((p for p in state.projects.projects if oid in p.objects), None)
            return {"project_code": p.code if p else None}

        new, removed = state.tree_diff
        body: dict[str, Any] = {
            "count": len(tree),
            "roots": len(tree.roots()),
            "new_since_last": [{"id": i, "path": " / ".join(tree.path(i))} for i in new],
            "removed_since_last": removed,
        }
        if flat:
            body["objects"] = [
                {
                    "id": i,
                    "path": " / ".join(tree.path(i)),
                    "parent_id": tree.parent_of(i),
                    "stage": tree.nodes[i].stage,
                    **{k: v for k, v in annotate(i).items() if v},
                }
                for i in tree.descendants(tree.roots())
            ]
        else:
            body["tree"] = tree.as_tree(annotate)
        return dumps(body)

    @mcp.resource(
        "tehzor://objects-tree",
        name="objects-tree",
        title="Дерево объектов компании",
        description="Дерево объектов компании (как objects_discover)",
        mime_type="application/json",
    )
    async def objects_tree() -> str:
        return dumps({"tree": (await get_tree(state)).as_tree()})

    @mcp.tool(
        name="problems_search",
        description="Нарушения по объектам с автопагинацией (до 2000). objects — UUID (старые id переводятся "
        "автоматически) и/или project — код проекта. include_children=true — с корпусами и секциями (сервер "
        "сам дочерние не учитывает). Компактный список: номер, объект, статус, вид работ, помещение, срок.",
        annotations=_ann("Поиск нарушений"),
        structured_output=False,
    )
    async def problems_search(
        objects: list[str] | None = None,
        project: str | None = None,
        include_children: bool = False,
        statuses: list[str] | None = None,
        spaces: list[str] | None = None,
        modified_at_from: str | None = None,
        modified_at_to: str | None = None,
        limit: int = 200,
    ) -> str:
        if limit < 1 or limit > s.search_max_items:
            raise ToolError(f"limit должен быть от 1 до {s.search_max_items}")
        try:
            ids, tree = await resolve_scope(state, objects, project, include_children)
            filters = ProblemFilters(
                objects=ids,
                statuses=statuses,
                spaces=spaces,
                modified_at_from=modified_at_from,
                modified_at_to=modified_at_to,
            )
            items = [p async for p in state.require_client().problems.iter(filters, max_items=limit)]
        except ToolError:
            raise
        except Exception as exc:
            raise tool_error(exc) from exc
        return dumps(
            {
                "items": [_compact_problem(p, tree) for p in items],
                "count": len(items),
                "objects": len(ids),
                "truncated": len(items) == limit,
            }
        )

    @mcp.tool(
        name="problems_summary",
        description="Сводка открытых нарушений: открыто, просрочено, критично — в разрезах object, category, "
        "contractor (организация из должности исполнителя), performer. Открыто: waiting/handling/verification; "
        "просрочено: открыто и срок устранения в прошлом (статус expired сервер не ставит). По текущему снимку — "
        "истории статусов в API нет. По исполнителю/организации одно нарушение попадает в несколько групп. "
        "include_children=true (по умолчанию) — с корпусами и секциями.",
        annotations=_ann("Сводка нарушений"),
        structured_output=False,
    )
    async def problems_summary(
        objects: list[str] | None = None,
        project: str | None = None,
        include_children: bool = True,
        group_by: list[str] | None = None,
        top: int = 20,
        max_items: int | None = None,
    ) -> str:
        dims = group_by or list(DIMENSIONS)
        bad = [d for d in dims if d not in DIMENSIONS]
        if bad:
            raise ToolError(f"неизвестный разрез {bad}; доступны: {', '.join(DIMENSIONS)}")
        budget = min(max_items or s.summary_max_items, s.summary_max_items)
        try:
            ids, tree = await resolve_scope(state, objects, project, include_children)
            per_object = max(50, budget // len(ids))
            client = state.require_client()

            async def fetch(oid: str) -> tuple[str, list[Problem]]:
                filters = ProblemFilters(objects=[oid], statuses=list(FETCH_STATUSES))
                return oid, [p async for p in client.problems.iter(filters, max_items=per_object + 1)]

            results = await asyncio.gather(*(fetch(i) for i in ids))
        except ToolError:
            raise
        except Exception as exc:
            raise tool_error(exc) from exc
        problems: list[Problem] = []
        truncated = []
        for oid, items in results:
            if len(items) > per_object:
                truncated.append({"id": oid, "name": _name(tree, oid), "fetched": per_object})
                items = items[:per_object]
            problems.extend(items)
        summary = summarize_problems(
            problems,
            now=datetime.now(timezone.utc),
            group_by=dims,
            top=top,
            object_name=(lambda oid: _name(tree, oid)) if tree is not None else None,
        )
        summary["scope"] = {"objects": len(ids), "include_children": include_children, "per_object_limit": per_object}
        if truncated:
            summary["truncated_objects"] = truncated
            summary["note"] = "по части объектов выборка упёрлась в лимит — цифры по ним нижняя граница"
        return dumps(summary)

    @mcp.tool(
        name="work_acceptances_search",
        description="Приёмки работ сразу по нескольким объектам (API принимает один объект за запрос — здесь "
        "объединяется). objects и/или project, include_children. statuses — список (waiting, in-progress, "
        "problems-identified, accepted, rejected). Даты — ISO 8601. Компактный список, новые сверху.",
        annotations=_ann("Поиск приёмок работ"),
        structured_output=False,
    )
    async def work_acceptances_search(
        objects: list[str] | None = None,
        project: str | None = None,
        include_children: bool = False,
        statuses: list[str] | None = None,
        created_at_from: str | None = None,
        created_at_to: str | None = None,
        modified_at_from: str | None = None,
        modified_at_to: str | None = None,
        limit: int = 200,
    ) -> str:
        if limit < 1 or limit > s.search_max_items:
            raise ToolError(f"limit должен быть от 1 до {s.search_max_items}")
        try:
            ids, tree = await resolve_scope(state, objects, project, include_children)
            dates = {
                "created_at_from": created_at_from,
                "created_at_to": created_at_to,
                "modified_at_from": modified_at_from,
                "modified_at_to": modified_at_to,
            }
            # fact: фильтр status принимает одно значение — несколько статусов = несколько запросов
            status_values: list[str | None] = list(statuses) if statuses else [None]
            filters = [WorkAcceptanceFilters(status=st, **dates) for st in status_values]
            client = state.require_client()

            async def fetch(oid: str, f: WorkAcceptanceFilters) -> list[WorkAcceptance]:
                return [w async for w in client.work_acceptances.iter(oid, f, max_items=limit)]

            batches = await asyncio.gather(*(fetch(oid, f) for oid in ids for f in filters))
        except ToolError:
            raise
        except Exception as exc:
            raise tool_error(exc) from exc
        merged = {w.id: w for batch in batches for w in batch}
        rows = sorted(
            merged.values(), key=lambda w: w.created_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True
        )
        truncated = len(rows) > limit or any(len(b) >= limit for b in batches)
        items = [
            {
                "id": w.id,
                "number": w.number,
                "object": _name(tree, w.object_id),
                "object_id": w.object_id,
                "status": w.status.name if w.status else None,
                "status_id": w.status.id if w.status else None,
                "category": w.category.name if w.category else None,
                "type": w.type,
                "front_type": w.front_type,
                "acceptance_interval_start": w.acceptance_interval_start.isoformat()
                if w.acceptance_interval_start
                else None,
                "acceptance_interval_end": w.acceptance_interval_end.isoformat() if w.acceptance_interval_end else None,
                "description": (w.description or "")[:200] or None,
            }
            for w in rows[:limit]
        ]
        return dumps({"items": items, "count": len(items), "objects": len(ids), "truncated": truncated})

    @mcp.tool(
        name="projects_list",
        description="Проекты из таблицы соответствий (TEHZOR_MCP_PROJECTS: каталог MD с frontmatter, JSON, YAML "
        "или CSV): код, название, объекты Техзора, карточка. Без настройки — пустой список.",
        annotations=_ann("Проекты"),
        structured_output=False,
    )
    async def projects_list() -> str:
        idx = state.projects
        idx.reload_if_changed()
        if not idx.configured:
            return dumps(
                {
                    "configured": False,
                    "projects": [],
                    "message": "соответствия проектов не заданы (TEHZOR_MCP_PROJECTS); объекты — objects_discover",
                }
            )
        return dumps({"configured": True, "projects": [p.as_dict() for p in idx.projects], "errors": idx.errors})

    @mcp.tool(
        name="project_resolve",
        description="Найти проект по коду (точно), по UUID объекта или по названию и вернуть его объекты Техзора "
        "(с дочерними при include_children) и карточку проекта.",
        annotations=_ann("Проект по коду"),
        structured_output=False,
    )
    async def project_resolve(query: str, include_children: bool = True) -> str:
        if not state.projects.configured:
            return dumps(
                {"configured": False, "matches": [], "message": "соответствия проектов не заданы (TEHZOR_MCP_PROJECTS)"}
            )
        found = state.projects.find(query)
        tree: ObjectTree | None = None
        if found and include_children:
            try:
                tree = await get_tree(state)
            except Exception as exc:
                raise tool_error(exc) from exc
        matches = []
        for p in found[:10]:
            ids = tree.descendants([tree.resolve(i) or i for i in p.objects]) if tree else p.objects
            matches.append({**p.as_dict(), "objects": [{"id": i, "path": _name(tree, i)} for i in ids]})
        return dumps({"configured": True, "matches": matches, "count": len(found)})
