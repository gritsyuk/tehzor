"""Уровень 2 (обратимый): собственник create → bind к тестовому помещению → unbind → delete.

Существующие собственники помещения не затрагиваются: unbindExistingOwners=false (true запрещён песочницей).
Изменяющие запросы разрешены только для собственника, созданного в прогоне, и для явно указанного
тестового помещения.

    TEHZOR_SANDBOX_SPACE_ID=<id> python -m tests.sandbox.level2_bind_space            # dry_run
    TEHZOR_SANDBOX_SPACE_ID=<id> python -m tests.sandbox.level2_bind_space --execute  # выполнить
"""

from __future__ import annotations

import argparse
import asyncio
import os
import secrets
import sys
import time
from pathlib import Path

from tehzor import TehzorClient
from tehzor.models.space_owners import SpaceOwnerCreate

from .guard import SandboxTransport, SandboxViolation, describe

ROOT = Path(__file__).parents[2]


async def main(execute: bool) -> int:
    space_id = os.environ.get("TEHZOR_SANDBOX_SPACE_ID")
    if not space_id:
        print("не задан TEHZOR_SANDBOX_SPACE_ID")
        return 2
    tag = f"[TEST tehzor-python {time.strftime('%Y-%m-%d')} {secrets.token_hex(3)}]"
    name = f"{tag} Тестовый собственник"
    journal = ROOT / "reports" / f"sandbox-level2-{time.strftime('%Y%m%d-%H%M%S')}.jsonl"
    t = SandboxTransport(journal, allowed_ids={space_id})
    async with TehzorClient(transport=t) as thz:
        so = thz.space_owners
        space = await thz.spaces.get(space_id)  # только чтение: помещение существует
        print(
            f"Тестовое помещение: id={space.id}, объект={space.object_id}, тип={space.type.id if space.type else None}"
        )
        before = await thz.spaces.owner_acceptances(space_id)
        print(f"Передач собственникам у помещения до теста: {len(before)}")

        if not execute:
            print("\nDRY RUN — ничего не отправляется\n")
            print("1. create:\n   ", describe(await so.create(SpaceOwnerCreate(name=name), dry_run=True)))
            print("2. bind:\n   ", describe(await so.bind("<id из шага 1>", space_id, dry_run=True)))
            print("3. unbind:\n   ", describe(await so.unbind("<id из шага 1>", space_id, dry_run=True)))
            print("4. delete:\n   ", describe(await so.delete("<id из шага 1>", dry_run=True)))
            for probe, kwargs in [
                ("чужое помещение", {"space_id": "000000000000000000000000"}),
                ("unbindExistingOwners=true", {"space_id": space_id, "unbind_existing_owners": True}),
            ]:
                try:
                    await so.bind("x", **kwargs)
                except SandboxViolation as exc:
                    print(f"Защита ({probe}):", exc)
            return 0

        print(f"\nЖурнал: {journal.relative_to(ROOT)}\nМетка: {tag}\n")
        oid: str | None = None
        bound = False
        try:
            created = await so.create(SpaceOwnerCreate(name=name, comment=f"{tag} уровень 2, будет удалён"))
            oid = created.id
            print(f"1. create: id={oid!r}, spaces={created.spaces}")
            if not oid:
                print("СТОП: нет id — удалите вручную по метке", tag)
                return 2
            t.track(oid, "space_owner")

            after_bind = await so.bind(oid, space_id, unbind_existing_owners=False)
            bound = True
            print(
                f"2. bind: spaces содержит помещение: {space_id in (after_bind.spaces or [])}, "
                f"spaces={after_bind.spaces}"
            )

            after_unbind = await so.unbind(oid, space_id)
            bound = space_id in (after_unbind.spaces or [])
            print(f"3. unbind: помещение отвязано: {not bound}, spaces={after_unbind.spaces}")
        finally:
            if oid and bound:
                try:
                    await so.unbind(oid, space_id)
                    print("   (повторный unbind в finally выполнен)")
                except Exception as exc:
                    print(f"   ОШИБКА повторного unbind: {exc}")
            if oid:
                try:
                    res = await so.delete(oid)
                    t.untrack(oid)
                    print(f"4. delete {oid}: ответ {sorted(res) if isinstance(res, dict) else res!r}")
                except Exception as exc:
                    print(f"4. delete {oid}: ОШИБКА {type(exc).__name__}: {exc}. Удалите вручную по метке {tag}")
        after = await thz.spaces.owner_acceptances(space_id)
        print(f"\nПередач собственникам у помещения после теста: {len(after)} (до: {len(before)})")
        if t.created:
            print("ОСТАЛИСЬ неудалённые:", sorted(t.created))
    return 0 if not t.created else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    sys.exit(asyncio.run(main(parser.parse_args().execute)))
