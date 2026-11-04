"""Контрактные тесты: живое API, СТРОГО только чтение.

Запуск:  pytest -m contract
Нужно:   доступ к api.tehzor.ru, ключ (TEHZOR_API_KEY или прокси, подставляющий заголовок api-key),
         TEHZOR_SEED_OBJECT_ID (один или несколько id объектов через запятую),
         TEHZOR_SEED_SPACE_ID (необязательно: помещения, проверяемые первыми, например с приборами учёта).
Опции:   TEHZOR_CONTRACT_REPORT=reports/contract   — записать отчёт (.md и .json)
         TEHZOR_CONTRACT_UPDATE_SNAPSHOTS=1        — обновить снимки фактических схем

Безопасность: клиент создаётся с read_only=True, а транспорт контрактного режима дополнительно
пропускает только операции реестра с kind == "R" (проверка по методу и пути, а не по HTTP-методу:
в Техзоре чтение списков идёт через POST .../get-*).
"""

from __future__ import annotations

import asyncio
import json
import os
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from tehzor import REGISTRY, TehzorClient
from tehzor._registry import Operation
from tehzor._transport import PreparedRequest, Transport
from tehzor.errors import ReadOnlyError
from tehzor.models.catalog import CheckListWithItems
from tehzor.models.comments import CommentFilters
from tehzor.models.problems import ProblemFilters
from tehzor.models.spaces import SpaceFilters
from tehzor.models.tasks import TaskFilters

from ._schema import compare_with_spec, drift, infer

ROOT = Path(__file__).parents[2]
SPEC = json.loads((ROOT / "docs" / "openapi.json").read_text(encoding="utf-8"))
SNAPSHOTS = Path(__file__).parent / "snapshots"
KNOWN_EXTRAS: dict[str, list[str]] = json.loads(
    (Path(__file__).parent / "known_extras.json").read_text(encoding="utf-8")
)
SAMPLE = 20


class ContractTransport(Transport):
    """Транспорт контрактного режима: только чтение + запись фактических ответов."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(read_only=True, rate_limit=2.0, max_concurrency=2, **kwargs)
        self.records: list[tuple[PreparedRequest, Any]] = []

    async def execute(self, op: Operation, **kwargs: Any) -> Any:
        registered = REGISTRY.get(op.method, op.path)
        if op.kind != "R" or registered is None or registered.kind != "R":
            raise ReadOnlyError(f"контрактные тесты: операция {op.method} {op.path} не является чтением")
        return await super().execute(op, **kwargs)

    async def send(self, req: PreparedRequest, *, can_retry: bool) -> Any:
        data = await super().send(req, can_retry=can_retry)
        self.records.append((req, data))
        return data


def make_client() -> TehzorClient:
    return TehzorClient(transport=ContractTransport(api_key=os.environ.get("TEHZOR_API_KEY") or None))


# --- обнаружение id по цепочке от объектов -------------------------------------------------------


@dataclass
class Ids:
    objects: list[str]
    problems: list[str] = field(default_factory=list)
    spaces: list[str] = field(default_factory=list)
    work_acceptances: list[str] = field(default_factory=list)
    internal_acceptances: list[str] = field(default_factory=list)
    owner_acceptances: list[str] = field(default_factory=list)
    warranty_claims: list[str] = field(default_factory=list)
    tasks: list[str] = field(default_factory=list)
    comments: list[str] = field(default_factory=list)
    checks: list[str] = field(default_factory=list)
    category_sets: list[str] = field(default_factory=list)
    tag_sets: list[str] = field(default_factory=list)
    check_lists: list[str] = field(default_factory=list)
    check_items: list[str] = field(default_factory=list)

    def need(self, name: str, n: int = 1) -> list[str]:
        values = getattr(self, name)
        if not values:
            pytest.skip(f"цепочка не нашла {name} в объектах seeds")
        return list(values[:n])


def _add(target: list[str], value: str | None) -> None:
    if value and value not in target:
        target.append(value)


async def discover(objects: list[str], spaces: list[str]) -> Ids:
    # помещения из seeds идут первыми: на них проверяются meters, owner_acceptances, warranty_claims
    ids = Ids(objects=objects, spaces=list(spaces))
    async with make_client() as c:
        for obj in objects:
            for p in await c.problems.list(ProblemFilters(objects=[obj]), limit=SAMPLE):
                _add(ids.problems, p.id)
                links = p.links
                if links:
                    _add(ids.spaces, links.space_id)
                    _add(ids.checks, links.check_id)
                    _add(ids.owner_acceptances, links.owner_acceptance_id)
                    _add(ids.warranty_claims, links.warranty_claim_id)
                    _add(ids.internal_acceptances, links.internal_acceptance_id)
                    _add(ids.work_acceptances, links.work_acceptance_id)
                    _add(ids.tasks, links.task_id)
            for s in await c.spaces.list(SpaceFilters(objects=[obj]), limit=SAMPLE):
                _add(ids.spaces, s.id)
            for w in await c.work_acceptances.list(obj, limit=SAMPLE):
                _add(ids.work_acceptances, w.id)
            for i in await c.internal_acceptances.list(obj, limit=SAMPLE):
                _add(ids.internal_acceptances, i.id)
            for t in await c.tasks.list(TaskFilters(objects=[obj]), limit=SAMPLE):
                _add(ids.tasks, t.id)
            for cs in await c.categories.sets(obj):
                _add(ids.category_sets, cs.id)
            for ts in await c.tags.sets(obj):
                _add(ids.tag_sets, ts.id)
            for cl in await c.check_lists.list(obj):
                _add(ids.check_lists, cl.id)
        for pid in ids.problems[:3]:
            for cm in await c.comments.list(CommentFilters(problem_id=pid), limit=SAMPLE):
                _add(ids.comments, cm.id)
        for sid in ids.spaces[:4]:
            for oa in await c.spaces.owner_acceptances(sid):
                _add(ids.owner_acceptances, oa.id)
            for wc in await c.spaces.warranty_claims(sid):
                _add(ids.warranty_claims, wc.id)
        for clid in ids.check_lists[:1]:
            full: CheckListWithItems = await c.check_lists.get(clid)
            for item in full.check_items or []:
                _add(ids.check_items, item.id)
    return ids


@pytest.fixture(scope="session")
def ids() -> Ids:
    raw = os.environ.get("TEHZOR_SEED_OBJECT_ID") or os.environ.get("TEHZOR_SEED_OBJECT_IDS")
    if not raw:
        pytest.skip("не задан TEHZOR_SEED_OBJECT_ID")
    spaces = os.environ.get("TEHZOR_SEED_SPACE_ID", "")
    return asyncio.run(discover(_split(raw), _split(spaces)))


def _split(value: str) -> list[str]:
    return [x.strip() for x in value.split(",") if x.strip()]


@pytest.fixture
async def live() -> AsyncIterator[TehzorClient]:
    async with make_client() as c:
        yield c


# --- отчёт ---------------------------------------------------------------------------------------


@dataclass
class Result:
    tool: str
    method: str
    path: str
    status: str
    items: int = 0
    extras: list[str] = field(default_factory=list)
    spec_diffs: list[str] = field(default_factory=list)
    drift: list[str] = field(default_factory=list)
    note: str = ""


class Report:
    def __init__(self) -> None:
        self.results: dict[str, Result] = {}

    def record(self, op: Operation, transport: ContractTransport, items: int, extras: list[str]) -> Result:
        raw = [data for req, data in transport.records if req.operation_id == op.operation_id
               and _matches(op.path, req.path)]
        values: list[Any] = []
        for data in raw:
            values.extend(data if isinstance(data, list) else [data])
        node = infer(raw)
        spec_diffs = compare_with_spec(SPEC, node, response_schema_for(op))
        snapshot = node.to_json()
        snap_file = SNAPSHOTS / f"{op.tool_name}.schema.json"
        drift_list: list[str] = []
        if snap_file.exists():
            drift_list = drift(json.loads(snap_file.read_text(encoding="utf-8")), snapshot)
        if os.environ.get("TEHZOR_CONTRACT_UPDATE_SNAPSHOTS") == "1" or not snap_file.exists():
            SNAPSHOTS.mkdir(exist_ok=True)
            snap_file.write_text(json.dumps(snapshot, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        result = Result(op.tool_name, op.method, op.path, "fail" if extras else "ok", items, extras,
                        spec_diffs, drift_list)
        self.results[op.tool_name] = result
        return result

    def skip(self, op: Operation, reason: str) -> None:
        self.results[op.tool_name] = Result(op.tool_name, op.method, op.path, "skip", note=reason)

    def write(self, base: Path) -> None:
        base.parent.mkdir(parents=True, exist_ok=True)
        rows = sorted(self.results.values(), key=lambda r: r.tool)
        base.with_suffix(".json").write_text(
            json.dumps([r.__dict__ for r in rows], ensure_ascii=False, indent=1), encoding="utf-8"
        )
        lines = [
            "# Контрактные тесты: факт vs модель vs спецификация",
            "",
            f"Спецификация: v{SPEC['info']['version']}. Только читающие операции.",
            "",
            "| Операция | Путь | Итог | Записей | Неописанные поля | Расхождения со spec | Дрейф |",
            "|---|---|---|---|---|---|---|",
        ]
        for r in rows:
            mark = {"ok": "ОК", "fail": "ПРОВАЛ", "skip": "пропуск"}[r.status]
            lines.append(f"| `{r.tool}` | `{r.method} {r.path}` | {mark}{(' — ' + r.note) if r.note else ''} "
                         f"| {r.items} | {len(r.extras)} | {len(r.spec_diffs)} | {len(r.drift)} |")
        for r in rows:
            if r.extras or r.spec_diffs or r.drift:
                lines += ["", f"## `{r.tool}`"]
                lines += [f"- **не описано в модели:** `{x}`" for x in r.extras]
                lines += [f"- дрейф: {x}" for x in r.drift]
                lines += [f"- spec: {x}" for x in r.spec_diffs]
        base.with_suffix(".md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _matches(template: str, path: str) -> bool:
    t, p = template.strip("/").split("/"), path.strip("/").split("/")
    return len(t) == len(p) and all(a.startswith("{") or a == b for a, b in zip(t, p, strict=True))


def response_schema_for(op: Operation) -> dict[str, Any] | None:
    from ._schema import response_schema

    return response_schema(SPEC, op.method, op.path)


@pytest.fixture(scope="session")
def report() -> Iterator[Report]:
    rep = Report()
    yield rep
    target = os.environ.get("TEHZOR_CONTRACT_REPORT")
    if target:
        rep.write(ROOT / target)
