"""Сводка по нарушениям по текущему снимку.

Правила (одно место для MCP и библиотеки):
* открыто — статусы waiting («К устранению»), handling («В работе»), verification («На проверке»);
  fixed («Устранено») и closed («Закрыто») — не открыты;
* просрочено — открыто и срок устранения (plannedFixDate) в прошлом, либо статус expired.
  fact (2026-11-05): статус expired в справочнике API отсутствует, фильтр по нему возвращает 0 — сервер
  просрочку статусом не отмечает, поэтому она считается по сроку;
* критично — признак critical.

Ограничения: история статусов в API отсутствует, поэтому метрик «устранено за период» нет — только снимок.
`reopened_times > 0` показывается отдельной цифрой. У нарушения несколько исполнителей (fact: 0–13), поэтому
в разрезах «исполнитель» и «организация» одно нарушение входит в несколько групп (multi_count).
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import Any

from ..models.common import User
from ..models.problems import Problem
from .contractors import contractor_from_position

OPEN_STATUSES = frozenset({"waiting", "handling", "verification"})
EXPIRED = "expired"
FETCH_STATUSES = [*sorted(OPEN_STATUSES), EXPIRED]
DIMENSIONS = ("object", "category", "contractor", "performer")
MULTI = frozenset({"contractor", "performer"})
RULES = {
    "open": "статус waiting, handling или verification (fixed и closed — устранены)",
    "overdue": "открыто и срок устранения в прошлом (или статус expired)",
    "critical": "признак critical",
    "snapshot": "по текущему состоянию; истории статусов в API нет",
}


def status_id(p: Problem) -> str | None:
    return p.status.id if p.status else None


def is_open(p: Problem) -> bool:
    return status_id(p) in OPEN_STATUSES or status_id(p) == EXPIRED


def is_overdue(p: Problem, now: datetime) -> bool:
    if status_id(p) == EXPIRED:
        return True
    return is_open(p) and p.planned_fix_date is not None and p.planned_fix_date < now


def _performers(p: Problem) -> list[User]:
    return [u for u in (p.performers or []) if isinstance(u, User)]


def _keys(p: Problem, dim: str, object_name: Any) -> list[tuple[str, str]]:
    if dim == "object":
        oid = p.object.id if p.object else "—"
        return [(oid, object_name(oid) if object_name else (p.object.name if p.object else "—") or oid)]
    if dim == "category":
        return [(p.category.id, p.category.name or p.category.id)] if p.category else [("—", "без вида работ")]
    if dim == "performer":
        users = _performers(p)
        result = {u.id: (u.full_name or u.display_name or u.id) for u in users}
        return list(result.items()) or [("—", "без исполнителя")]
    if dim == "contractor":
        found: dict[str, str] = {}
        for u in _performers(p):
            c = contractor_from_position(u.position)
            if c:
                found.setdefault(c[1], c[0])
        return [(k, v) for k, v in found.items()] or [("—", "организация не определена")]
    raise ValueError(f"неизвестный разрез {dim!r}; доступны: {', '.join(DIMENSIONS)}")


def summarize_problems(
    problems: Iterable[Problem],
    *,
    now: datetime,
    group_by: Iterable[str] = DIMENSIONS,
    top: int = 20,
    object_name: Any = None,
) -> dict[str, Any]:
    dims = list(group_by)
    for d in dims:
        if d not in DIMENSIONS:
            raise ValueError(f"неизвестный разрез {d!r}; доступны: {', '.join(DIMENSIONS)}")
    totals = {"problems": 0, "open": 0, "overdue": 0, "critical": 0, "critical_overdue": 0, "reopened": 0}
    groups: dict[str, dict[str, dict[str, Any]]] = {d: {} for d in dims}
    for p in problems:
        totals["problems"] += 1
        if not is_open(p):
            continue
        overdue = is_overdue(p, now)
        critical = bool(p.critical)
        totals["open"] += 1
        totals["overdue"] += overdue
        totals["critical"] += critical
        totals["critical_overdue"] += critical and overdue
        totals["reopened"] += bool(p.reopened_times)
        for d in dims:
            # contractor: одна организация учитывается в нарушении один раз, даже при нескольких её сотрудниках
            for key, name in _keys(p, d, object_name):
                g = groups[d].setdefault(key, {"key": key, "name": name, "open": 0, "overdue": 0, "critical": 0})
                g["open"] += 1
                g["overdue"] += overdue
                g["critical"] += critical
    out_groups: dict[str, Any] = {}
    for d in dims:
        items = sorted(groups[d].values(), key=lambda g: (-g["overdue"], -g["open"], str(g["name"])))
        out_groups[d] = {"groups_total": len(items), "items": items[:top], "multi_count": d in MULTI}
        if d in MULTI:
            out_groups[d]["note"] = ("у нарушения бывает несколько исполнителей — сумма по группам может быть "
                                     "больше общего числа нарушений")
    return {"rules": RULES, "now": now.isoformat(), "totals": totals, "groups": out_groups}
