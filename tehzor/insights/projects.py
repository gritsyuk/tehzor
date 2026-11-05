"""Соответствие «объект Техзора → проект» (код, название, карточка).

Источник задаётся путём (в MCP — `TEHZOR_MCP_PROJECTS`):

* каталог `.md` (граф знаний): у файла проекта YAML-frontmatter, например
  ```
  ---
  code: SIG
  title: ЖК «Аквилон Signal»
  tehzor: 00000000-0000-4000-8000-000000000001   # или список UUID; ключи tehzor_objects / tehzor_object_id
  ---
  Описание проекта…
  ```
  Карточка — путь к файлу и первый абзац описания. Без `code` кодом считается имя файла. Файлы без
  frontmatter с `code` или `tehzor*` пропускаются (это просто заметки);
* `.json` / `.yaml` / `.yml`: список записей `{code, name, objects: [uuid…], card}` или словарь `code → запись`;
* `.csv`: колонки `object_id, project_code, project_name, card` (строка на объект).

Без источника индекс пуст — инструменты работают как обычно, просто без кодов проектов.
Файлы перечитываются при изменении (по времени модификации).
"""

from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

OBJECT_KEYS = ("tehzor", "tehzor_objects", "tehzor_object_id", "tehzor_object", "objects")
CODE_KEYS = ("code", "project_code", "id")
NAME_KEYS = ("title", "name", "project_name")


@dataclass
class Project:
    code: str
    name: str | None = None
    objects: list[str] = field(default_factory=list)
    card: str | None = None
    description: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if v not in (None, [], "")}


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(v).strip() for v in value if str(v).strip()]
    return [v.strip() for v in str(value).split(",") if v.strip()]


def _first(d: dict[str, Any], keys: tuple[str, ...]) -> Any:
    return next((d[k] for k in keys if d.get(k) not in (None, "")), None)


def _load_frontmatter(text: str) -> Any:
    """Frontmatter MD: PyYAML, если установлен, иначе простой разбор (key: value, списки) — его хватает."""
    try:
        import yaml
    except ImportError:
        return _mini_yaml(text)
    return yaml.safe_load(text)


def _load_yaml_file(text: str) -> Any:
    """Файл .yaml/.yml — только PyYAML: упрощённый разбор не понимает списки записей и дал бы пустой индекс."""
    try:
        import yaml
    except ImportError:
        raise RuntimeError(
            'для файла .yaml нужен PyYAML: pip install "tehzor[mcp]" (или pyyaml); либо используйте JSON, CSV или MD'
        ) from None
    return yaml.safe_load(text)


def _mini_yaml(text: str) -> dict[str, Any]:
    """Простой разбор frontmatter без PyYAML: `key: value`, `key: [a, b]`, списки `- item`."""
    data: dict[str, Any] = {}
    current: str | None = None
    for raw in text.splitlines():
        line = raw.split(" #", 1)[0].rstrip()
        if not line.strip():
            continue
        item = re.match(r"^\s*-\s+(.*)$", line)
        if item and current:
            data.setdefault(current, [])
            if isinstance(data[current], list):
                data[current].append(item.group(1).strip().strip("'\""))
            continue
        kv = re.match(r"^([\w.-]+)\s*:\s*(.*)$", line)
        if kv:
            current, value = kv.group(1), kv.group(2).strip()
            if value.startswith("[") and value.endswith("]"):
                data[current] = [v.strip().strip("'\"") for v in value[1:-1].split(",") if v.strip()]
            elif value:
                data[current] = value.strip("'\"")
            else:
                data[current] = []
    return data


def _record(d: dict[str, Any], default_code: str | None = None, card: str | None = None) -> Project | None:
    code = _first(d, CODE_KEYS) or default_code
    objects = _as_list(_first(d, OBJECT_KEYS))
    if not code:
        return None
    return Project(code=str(code).strip(), name=_first(d, NAME_KEYS), objects=objects,
                   card=_first(d, ("card", "url", "path")) or card)


def _from_markdown(path: Path) -> Project | None:
    text = path.read_text(encoding="utf-8", errors="replace")
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", text, re.S)
    if not m:
        return None
    meta = _load_frontmatter(m.group(1))
    if not isinstance(meta, dict):
        return None
    if not (_first(meta, CODE_KEYS) or _first(meta, OBJECT_KEYS)):
        return None
    project = _record(meta, default_code=path.stem, card=str(path))
    if project is None:
        return None
    body = [b.strip() for b in re.split(r"\n\s*\n", m.group(2)) if b.strip() and not b.strip().startswith("#")]
    if body:
        project.description = re.sub(r"\s+", " ", body[0])[:500]
    if not project.name:
        heading = re.search(r"^#\s+(.+)$", m.group(2), re.M)
        project.name = heading.group(1).strip() if heading else None
    return project


def _from_table(path: Path) -> list[Project]:
    if path.suffix.lower() == ".csv":
        projects: dict[str, Project] = {}
        with path.open(encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                code = (row.get("project_code") or row.get("code") or "").strip()
                if not code:
                    continue
                p = projects.setdefault(code, Project(code=code))
                p.name = p.name or (row.get("project_name") or row.get("name") or None)
                p.card = p.card or (row.get("card") or None)
                p.objects.extend(_as_list(row.get("object_id") or row.get("objects")))
        return list(projects.values())
    text = path.read_text(encoding="utf-8")
    data = json.loads(text) if path.suffix.lower() == ".json" else _load_yaml_file(text)
    if isinstance(data, dict):
        data = [{"code": k, **(v if isinstance(v, dict) else {"objects": v})} for k, v in data.items()]
    result = []
    for d in data or []:
        if isinstance(d, dict):
            rec = _record(d)
            if rec:
                result.append(rec)
    return result


class ProjectsIndex:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path
        self.projects: list[Project] = []
        self.errors: list[str] = []
        self._stamp: float | None = None
        self.reload_if_changed()

    @property
    def configured(self) -> bool:
        return self.path is not None

    def _mtime(self) -> float:
        if self.path is None or not self.path.exists():
            return 0.0
        if self.path.is_dir():
            return max((p.stat().st_mtime for p in self.path.rglob("*.md")), default=self.path.stat().st_mtime)
        return self.path.stat().st_mtime

    def reload_if_changed(self) -> None:
        stamp = self._mtime()
        if stamp == self._stamp:
            return
        self._stamp = stamp
        self.projects, self.errors = [], []
        if self.path is None:
            return
        if not self.path.exists():
            self.errors.append(f"путь не найден: {self.path}")
            return
        files = sorted(self.path.rglob("*.md")) if self.path.is_dir() else [self.path]
        for f in files:
            try:
                if f.suffix.lower() == ".md":
                    p = _from_markdown(f)
                    if p:
                        self.projects.append(p)
                else:
                    self.projects.extend(_from_table(f))
            except Exception as exc:
                self.errors.append(f"{f}: {exc}")

    def find(self, query: str) -> list[Project]:
        """По коду (точно, без учёта регистра), по UUID объекта, затем по названию (подстрока)."""
        self.reload_if_changed()
        q = query.strip().casefold()
        exact = [p for p in self.projects if p.code.casefold() == q]
        if exact:
            return exact
        by_object = [p for p in self.projects if query.strip() in p.objects]
        if by_object:
            return by_object
        return [p for p in self.projects if q and (q in (p.name or "").casefold() or q in p.code.casefold())]

    def for_object(self, object_id: str, ancestors: list[str] | None = None) -> Project | None:
        """Проект объекта; если объект не размечен — ближайшего размеченного родителя."""
        self.reload_if_changed()
        for candidate in [object_id, *(ancestors or [])]:
            for p in self.projects:
                if candidate in p.objects:
                    return p
        return None
