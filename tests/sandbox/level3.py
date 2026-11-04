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
from pathlib import Path
from typing import Any

from tehzor import PreparedRequest, TehzorClient
from tehzor.enums import ProcessId, Stage
from tehzor.models.problems import ProblemCreate

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


STEPS: dict[str, Step] = {
    "problem-building-create": problem_building_create,
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
