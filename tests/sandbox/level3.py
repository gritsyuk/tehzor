"""Уровень 3 — по шагам, под наблюдением человека в веб-интерфейсе.

Создаёт сущности, которые через API удалить нельзя (остаются в объекте, закрываются статусом).
Изменять можно только созданное в этом сценарии (id сохраняются в reports/sandbox-level3-state.json).
Ссылки в теле (objectId, spaceId, links.spaceId) — только на тестовые объект и помещение.

    TEHZOR_SANDBOX_OBJECT_ID=… TEHZOR_SANDBOX_SPACE_ID=… python -m tests.sandbox.level3 <шаг>            # dry_run
    TEHZOR_SANDBOX_OBJECT_ID=… TEHZOR_SANDBOX_SPACE_ID=… python -m tests.sandbox.level3 <шаг> --execute  # выполнить
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from tehzor import PreparedRequest, TehzorClient
from tehzor.enums import CommentType, ProblemStatus, ProcessId, Stage
from tehzor.models.comments import CommentCreate, CommentFilters, CommentLinksInput
from tehzor.models.problems import ProblemCreate, ProblemEdit
from tehzor.models.spaces import SpaceEdit

from .guard import SandboxTransport, describe

ROOT = Path(__file__).parents[2]
STATE = ROOT / "reports" / "sandbox-level3-state.json"
WEB = "https://app.tehzor.ru"
DATE = time.strftime("%Y-%m-%d")


def load_state() -> dict[str, Any]:
    if STATE.exists():
        return json.loads(STATE.read_text(encoding="utf-8"))
    return {"tag": f"[TEST tehzor-python {DATE}]", "created": {}}


def save_state(state: dict[str, Any]) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")


class Ctx:
    def __init__(self, thz: TehzorClient, t: SandboxTransport, state: dict[str, Any], obj: str, space: str) -> None:
        self.thz, self.t, self.state, self.obj, self.space = thz, t, state, obj, space

    @property
    def tag(self) -> str:
        return str(self.state["tag"])

    def created(self, key: str) -> str:
        value = self.state["created"].get(key)
        if not value:
            raise SystemExit(f"сначала выполните шаг, создающий «{key}»")
        return str(value)

    def remember(self, key: str, entity_id: str | None) -> None:
        if entity_id:
            self.state["created"][key] = entity_id
            self.t.track(entity_id, key)
            save_state(self.state)


Step = Callable[[Ctx, bool], Awaitable[Any]]
CATEGORY_BUILDING = "638d7e84c0ea064d70658564"  # «Кладка и перегородки», набор «Единый классификатор (Аквилон)»


async def problem_building_create(c: Ctx, dry: bool) -> Any:
    data = ProblemCreate(
        object_id=c.obj,
        stage=Stage.BUILDING,
        process_id=ProcessId.OPERATIONAL_CONTROL,
        category_id=CATEGORY_BUILDING,
        description=f"{c.tag} Тестовое нарушение (стадия строительства). Создано автотестом библиотеки tehzor, "
        "исполнять не нужно.",
    )
    result = await c.thz.problems.create(data, dry_run=dry)
    if not dry:
        c.remember("problem_building", result.id)
        print(f"   id={result.id} номер={result.number} статус={result.status.name if result.status else None}")
        print(f"   веб: {WEB}/objects/{c.obj}/problems/{result.id}")
    return result


async def _show_problem(c: Ctx, pid: str) -> None:
    p = await c.thz.problems.get(pid)
    print(
        f"   сейчас: номер={p.number} статус={p.status.id if p.status else None} "
        f"срок={p.planned_fix_date} вид работ={p.category.name if p.category else None}"
    )
    print(f"   описание: {p.description}")


async def problem_building_edit(c: Ctx, dry: bool) -> Any:
    pid = c.created("problem_building")
    due = datetime.now(timezone.utc).replace(hour=12, minute=0, second=0, microsecond=0) + timedelta(days=30)
    data = ProblemEdit(
        description=f"{c.tag} Тестовое нарушение (стадия строительства) — ИЗМЕНЕНО шагом 3.2. "
        "Создано автотестом библиотеки tehzor, исполнять не нужно.",
        planned_fix_date=due,
    )
    if dry:
        await _show_problem(c, pid)
    result = await c.thz.problems.edit(pid, data, dry_run=dry)
    if not dry:
        await _show_problem(c, pid)
    return result


async def problem_building_comment(c: Ctx, dry: bool) -> Any:
    pid = c.created("problem_building")
    data = CommentCreate(
        comment_type_id=CommentType.PROBLEM_COMMENT,
        links=CommentLinksInput(problem_id=pid),
        official=False,
        description=f"{c.tag} Тестовый комментарий (шаг 3.3).",
    )
    result = await c.thz.comments.create(data, dry_run=dry)
    if not dry:
        c.remember("comment_building", result.id)
        found = await c.thz.comments.list(CommentFilters(problem_id=pid))
        print(f"   комментарий id={result.id}; комментариев у нарушения: {len(found)}")
    return result


async def problem_building_close(c: Ctx, dry: bool) -> Any:
    pid = c.created("problem_building")
    result = await c.thz.problems.edit(pid, ProblemEdit(status=ProblemStatus.CLOSED), dry_run=dry)
    if not dry:
        await _show_problem(c, pid)
    return result


# --- группа C: тестовое помещение (обратимо, значения восстановления — только из снимка) -------------

VOLATILE = {"modifiedAt", "modifiedBy"}


async def _space_dump(c: Ctx) -> dict[str, Any]:
    space = await c.thz.spaces.get(c.space)
    return space.model_dump(by_alias=True, exclude_none=True, mode="json")


def _diff(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    keys = (set(before) | set(after)) - VOLATILE
    return {k: (before.get(k), after.get(k)) for k in sorted(keys) if before.get(k) != after.get(k)}


def _snapshot(c: Ctx) -> dict[str, Any]:
    snap = c.state.get("original_space")
    if not snap or snap.get("id") != c.space:
        raise SystemExit("нет снимка помещения — сначала выполните шаг space-snapshot")
    return dict(snap)


async def space_snapshot(c: Ctx, dry: bool) -> Any:
    """Только чтение: сохраняет исходное состояние помещения для восстановления."""
    if c.state.get("original_space"):
        print("   снимок уже есть — не перезаписываю (иначе потеряем исходные значения)")
        return None
    dump = await _space_dump(c)
    status = await c.thz.spaces.get_status(c.space)
    dump["_status_id"] = status.id
    print(f"   plannedArea={dump.get('plannedArea')!r} статус={status.id} ({status.name})")
    if not dry:
        c.state["original_space"] = dump
        save_state(c.state)
        print("   снимок сохранён в reports/sandbox-level3-state.json")
    return None


async def space_edit(c: Ctx, dry: bool) -> Any:
    snap = _snapshot(c)
    result = await c.thz.spaces.edit(c.space, SpaceEdit(planned_area=12.34), dry_run=dry)
    if not dry:
        print(
            "   изменения относительно снимка:",
            _diff({k: v for k, v in snap.items() if not k.startswith("_")}, await _space_dump(c)),
        )
    return result


async def space_edit_restore(c: Ctx, dry: bool) -> Any:
    snap = _snapshot(c)
    original = snap.get("plannedArea")
    if original is None:
        raise SystemExit("в снимке нет plannedArea — восстановить нечем")
    result = await c.thz.spaces.edit(c.space, SpaceEdit(planned_area=original), dry_run=dry)
    if not dry:
        diff = _diff({k: v for k, v in snap.items() if not k.startswith("_")}, await _space_dump(c))
        print("   отличия от снимка после восстановления:", diff or "нет — помещение как было")
    return result


SPACE_STATUS_TEST = "6444e362d28e6c2b2bbf92aa"  # «Не осмотрено», стадия acceptance


async def space_status(c: Ctx, dry: bool) -> Any:
    snap = _snapshot(c)
    if snap["_status_id"] == SPACE_STATUS_TEST:
        raise SystemExit("тестовый статус совпадает с исходным — выберите другой")
    result = await c.thz.spaces.set_status(c.space, SPACE_STATUS_TEST, dry_run=dry)
    if not dry:
        st = await c.thz.spaces.get_status(c.space)
        print(f"   статус сейчас: {st.id} ({st.name})")
    return result


async def space_status_restore(c: Ctx, dry: bool) -> Any:
    snap = _snapshot(c)
    result = await c.thz.spaces.set_status(c.space, snap["_status_id"], dry_run=dry)
    if not dry:
        st = await c.thz.spaces.get_status(c.space)
        print(f"   статус сейчас: {st.id} ({st.name}); совпадает со снимком: {st.id == snap['_status_id']}")
    return result


STEPS: dict[str, Step] = {
    "problem-building-create": problem_building_create,
    "problem-building-edit": problem_building_edit,
    "problem-building-comment": problem_building_comment,
    "problem-building-close": problem_building_close,
    "space-snapshot": space_snapshot,
    "space-edit": space_edit,
    "space-edit-restore": space_edit_restore,
    "space-status": space_status,
    "space-status-restore": space_status_restore,
}


async def main(step: str, execute: bool) -> int:
    obj = os.environ.get("TEHZOR_SANDBOX_OBJECT_ID")
    space = os.environ.get("TEHZOR_SANDBOX_SPACE_ID")
    if not obj or not space:
        print("нужны TEHZOR_SANDBOX_OBJECT_ID и TEHZOR_SANDBOX_SPACE_ID")
        return 2
    state = load_state()
    journal = ROOT / "reports" / "sandbox-level3.jsonl"
    t = SandboxTransport(journal, allowed_ids={obj, space})
    for key, value in state["created"].items():
        t.track(value, f"(из состояния) {key}")
    async with TehzorClient(transport=t) as thz:
        ctx = Ctx(thz, t, state, obj, space)
        print(f"Шаг: {step} | {'ВЫПОЛНЕНИЕ' if execute else 'DRY RUN — ничего не отправляется'}")
        if not execute:
            prepared = await STEPS[step](ctx, True)
            if isinstance(prepared, PreparedRequest):
                print("   " + describe(prepared))
            return 0
        await STEPS[step](ctx, False)
    print(f"Создано в сценарии: {state['created']}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("step", choices=sorted(STEPS))
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    sys.exit(asyncio.run(main(args.step, args.execute)))
