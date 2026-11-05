"""Аналитика (tehzor.insights): дерево объектов, организации исполнителей, сводка, проекты. Без сети."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from aioresponses import aioresponses

from tehzor import TehzorClient
from tehzor.insights import (
    ObjectTree,
    ProjectsIndex,
    contractor_from_position,
    discover_objects,
    is_open,
    is_overdue,
    snapshot_diff,
    summarize_problems,
)
from tehzor.models.objects import ConstructionObject
from tehzor.models.problems import Problem
from tests.conftest import BASE

ROOT = "00000000-0000-4000-8000-000000000001"
K1 = "00000000-0000-4000-8000-000000000002"
S1 = "00000000-0000-4000-8000-000000000003"
OTHER = "00000000-0000-4000-8000-000000000004"
NOW = datetime(2026, 11, 5, 12, tzinfo=timezone.utc)


def obj(i: str, name: str, parent: str | None = None, ext: str | None = None) -> ConstructionObject:
    return ConstructionObject(id=i, name=name, parent_id=parent, external_id=ext)


def tree() -> ObjectTree:
    return ObjectTree([obj(ROOT, "ЖК Тест", ext="aaaaaaaaaaaaaaaaaaaaaaaa"), obj(K1, "Корпус 1", ROOT),
                       obj(S1, "Секция 1", K1), obj(OTHER, "ЖК Другой")])


# --- дерево ---------------------------------------------------------------------------------------


def test_tree_structure_and_paths() -> None:
    t = tree()
    assert t.roots() == [OTHER, ROOT]  # по названию
    assert t.descendants([ROOT]) == [ROOT, K1, S1]
    assert t.descendants([ROOT], include_self=False) == [K1, S1]
    assert t.path(S1) == ["ЖК Тест", "Корпус 1", "Секция 1"]
    assert t.ancestors(S1) == [K1, ROOT]


def test_tree_resolves_old_external_id() -> None:
    t = tree()
    assert t.resolve("aaaaaaaaaaaaaaaaaaaaaaaa") == ROOT
    assert t.resolve(K1) == K1
    assert t.resolve("bbbbbbbbbbbbbbbbbbbbbbbb") is None


def test_parent_given_as_external_id() -> None:
    t = ObjectTree([obj(ROOT, "ЖК", ext="aaaaaaaaaaaaaaaaaaaaaaaa"), obj(K1, "К1", "aaaaaaaaaaaaaaaaaaaaaaaa")])
    assert t.children(ROOT) == [K1]


def test_snapshot_diff(tmp_path: Path) -> None:
    path = tmp_path / "objects.json"
    assert snapshot_diff(ObjectTree([obj(ROOT, "ЖК")]), path) == ([], [])  # первый обход — без сравнения
    assert snapshot_diff(ObjectTree([obj(ROOT, "ЖК"), obj(K1, "Новый")]), path) == ([K1], [])
    assert snapshot_diff(ObjectTree([obj(K1, "Новый")]), path) == ([], [ROOT])


async def test_discover_objects_from_sets_and_check_lists(mocked: aioresponses) -> None:
    mocked.get(f"{BASE}/categories-sets", payload=[{"id": "cs", "objects": [K1]}])
    mocked.get(f"{BASE}/tags-sets", payload=[{"id": "ts", "objects": [S1]}])
    mocked.get(f"{BASE}/check-lists", payload=[{"id": "cl", "objects": [{"id": S1, "name": "Секция 1"}]}])
    mocked.get(f"{BASE}/objects/{K1}", payload={"id": K1, "name": "Корпус 1", "parentId": ROOT})
    mocked.get(f"{BASE}/objects/{S1}", payload={"id": S1, "name": "Секция 1", "parentId": K1})
    # родителя нет в источниках — дочитывается отдельно
    mocked.get(f"{BASE}/objects/{ROOT}", payload={"id": ROOT, "name": "ЖК Тест"})
    async with TehzorClient(api_key="k", rate_limit=0) as c:
        t = await discover_objects(c)
    assert len(t) == 3 and t.roots() == [ROOT] and t.descendants([ROOT]) == [ROOT, K1, S1]


# --- организации исполнителей -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("position", "key"),
    [
        ("Производитель работ, Альфа Строй", "альфа строй"),
        ("Руководитель проекта, ООО «Альфа Строй»", "альфа строй"),
        ("Генподряд, ООО \"Бета\"", "бета"),
        ("ООО \"Бета\"", "бета"),
        ("Инженер-энергетик, ООО \"Бета\"", "бета"),
        ("Подрядчик, ООО ”Гамма-Конструкция\"", "гамма-конструкция"),
        ("Технадзор, АО «Дельта»", "дельта"),
        ("Инженер гарантийного отдела", None),
        ("", None),
        (None, None),
    ],
)
def test_contractor_from_position(position: str | None, key: str | None) -> None:
    result = contractor_from_position(position)
    assert (result[1] if result else None) == key


# --- сводка ---------------------------------------------------------------------------------------


def prob(i: str, status: str, *, due: datetime | None = None, critical: bool = False, obj_id: str = S1,
         performers: list[dict[str, str]] | None = None, category: str | None = "Окна") -> Problem:
    data: dict[str, object] = {"id": i, "status": {"id": status}, "object": {"id": obj_id, "name": "Секция 1"},
                               "critical": critical, "performers": performers or []}
    if due:
        data["plannedFixDate"] = int(due.timestamp() * 1000)
    if category:
        data["category"] = {"id": category, "name": category}
    return Problem.model_validate(data)


@pytest.mark.parametrize(
    ("status", "due_delta", "open_", "overdue"),
    [
        ("waiting", -1, True, True), ("handling", -1, True, True), ("verification", 1, True, False),
        ("fixed", -1, False, False), ("closed", -1, False, False), ("expired", 5, True, True),
        ("waiting", None, True, False),
    ],
)
def test_open_and_overdue_rules(status: str, due_delta: int | None, open_: bool, overdue: bool) -> None:
    p = prob("p", status, due=NOW + timedelta(days=due_delta) if due_delta is not None else None)
    assert is_open(p) is open_
    assert is_overdue(p, NOW) is overdue


def test_summary_totals_and_groups() -> None:
    a = {"id": "u1", "fullName": "Иванов", "position": "Прораб, ООО «Альфа»"}
    b = {"id": "u2", "fullName": "Петров", "position": "Инженер, ООО \"Альфа\""}
    c = {"id": "u3", "fullName": "Сидоров", "position": "Инженер гарантийного отдела"}
    problems = [
        prob("1", "waiting", due=NOW - timedelta(days=3), critical=True, performers=[a, b]),
        prob("2", "handling", due=NOW + timedelta(days=3), performers=[c]),
        prob("3", "closed", due=NOW - timedelta(days=9), performers=[a]),
        prob("4", "verification", category=None),
    ]
    out = summarize_problems(problems, now=NOW, group_by=["category", "contractor", "performer"])
    assert out["totals"] == {"problems": 4, "open": 3, "overdue": 1, "critical": 1, "critical_overdue": 1,
                             "reopened": 0}
    cats = {g["name"]: g for g in out["groups"]["category"]["items"]}
    assert cats["Окна"]["open"] == 2 and cats["без вида работ"]["open"] == 1
    contractors = {g["key"]: g for g in out["groups"]["contractor"]["items"]}
    assert contractors["альфа"]["open"] == 1  # два сотрудника одной организации — одно нарушение
    assert contractors["—"]["open"] == 2
    perf = out["groups"]["performer"]
    assert perf["multi_count"] and sum(g["open"] for g in perf["items"]) == 4 > out["totals"]["open"]
    assert "rules" in out and out["groups"]["category"]["multi_count"] is False


def test_summary_rejects_unknown_dimension() -> None:
    with pytest.raises(ValueError):
        summarize_problems([], now=NOW, group_by=["unknown"])


# --- проекты --------------------------------------------------------------------------------------


def test_projects_absent_config() -> None:
    idx = ProjectsIndex(None)
    assert not idx.configured and idx.projects == [] and idx.find("SIG") == []


def test_projects_markdown_graph(tmp_path: Path) -> None:
    (tmp_path / "projects").mkdir()
    (tmp_path / "projects" / "signal.md").write_text(
        f"---\ncode: SIG\ntitle: ЖК Сигнал\ntehzor:\n  - {ROOT}\n---\n# Сигнал\n\nЖилой комплекс у метро.\n",
        encoding="utf-8")
    (tmp_path / "projects" / "park.md").write_text(f"---\ntehzor_object_id: {OTHER}\n---\nПарк.\n", encoding="utf-8")
    (tmp_path / "projects" / "note.md").write_text("Просто заметка без frontmatter", encoding="utf-8")
    idx = ProjectsIndex(tmp_path / "projects")
    assert sorted(p.code for p in idx.projects) == ["SIG", "park"]  # без code — имя файла
    sig = idx.find("sig")[0]
    assert sig.objects == [ROOT] and sig.name == "ЖК Сигнал" and sig.description == "Жилой комплекс у метро."
    assert sig.card and sig.card.endswith("signal.md")
    assert idx.find(OTHER)[0].code == "park"
    assert idx.for_object(S1, [K1, ROOT]).code == "SIG"  # type: ignore[union-attr]  # через родителя


def test_projects_minimal_yaml_without_pyyaml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import builtins

    real_import = builtins.__import__

    def no_yaml(name: str, *args: object, **kwargs: object) -> object:
        if name == "yaml":
            raise ImportError
        return real_import(name, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(builtins, "__import__", no_yaml)
    (tmp_path / "p.md").write_text(f"---\ncode: SIG  # комментарий\ntehzor: [{ROOT}, {OTHER}]\n---\nТекст\n",
                                   encoding="utf-8")
    assert ProjectsIndex(tmp_path).find("SIG")[0].objects == [ROOT, OTHER]


def test_yaml_file_without_pyyaml_reports_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Без PyYAML файл .yaml не должен молча давать пустой индекс (так упал CI 0.3.0)."""
    import builtins

    real_import = builtins.__import__

    def no_yaml(name: str, *args: object, **kwargs: object) -> object:
        if name == "yaml":
            raise ImportError
        return real_import(name, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(builtins, "__import__", no_yaml)
    (tmp_path / "p.yaml").write_text(f"- code: PARK\n  objects: [{OTHER}]\n", encoding="utf-8")
    idx = ProjectsIndex(tmp_path / "p.yaml")
    assert idx.projects == [] and idx.errors and "PyYAML" in idx.errors[0]


def test_projects_json_csv_yaml(tmp_path: Path) -> None:
    (tmp_path / "p.json").write_text(json.dumps({"SIG": {"name": "Сигнал", "objects": [ROOT]}}), encoding="utf-8")
    assert ProjectsIndex(tmp_path / "p.json").find("SIG")[0].objects == [ROOT]
    (tmp_path / "p.csv").write_text(f"object_id,project_code,project_name\n{ROOT},SIG,Сигнал\n{K1},SIG,\n",
                                    encoding="utf-8")
    assert ProjectsIndex(tmp_path / "p.csv").find("SIG")[0].objects == [ROOT, K1]
    pytest.importorskip("yaml")
    (tmp_path / "p.yaml").write_text(f"- code: PARK\n  objects: [{OTHER}]\n", encoding="utf-8")
    assert ProjectsIndex(tmp_path / "p.yaml").find("park")[0].objects == [OTHER]


def test_projects_reload_on_change(tmp_path: Path) -> None:
    import os

    f = tmp_path / "p.json"
    f.write_text(json.dumps([{"code": "A", "objects": [ROOT]}]), encoding="utf-8")
    idx = ProjectsIndex(f)
    assert idx.find("A")
    f.write_text(json.dumps([{"code": "B", "objects": [ROOT]}]), encoding="utf-8")
    os.utime(f, (f.stat().st_atime, f.stat().st_mtime + 5))
    assert idx.find("B") and not idx.find("A")


def test_broken_file_does_not_break_index(tmp_path: Path) -> None:
    (tmp_path / "bad.md").write_text("---\ncode: [unclosed\n---\n", encoding="utf-8")
    (tmp_path / "ok.md").write_text("---\ncode: OK\n---\n", encoding="utf-8")
    idx = ProjectsIndex(tmp_path)
    assert idx.find("OK")
