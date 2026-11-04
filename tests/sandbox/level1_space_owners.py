"""Уровень 1 (полностью обратимый): собственник create → edit → get_or_create → delete.

Ничего существующего не изменяется: собственник создаётся без привязки к помещениям,
все изменяющие запросы проходят через SandboxTransport (только id, созданные в этом прогоне).

    python -m tests.sandbox.level1_space_owners            # dry_run: показать запросы, ничего не отправлять
    python -m tests.sandbox.level1_space_owners --execute  # выполнить (только после подтверждения человеком)
"""

from __future__ import annotations

import argparse
import asyncio
import secrets
import sys
import time
from pathlib import Path

from tehzor import TehzorClient
from tehzor.models.space_owners import SpaceOwnerCreate, SpaceOwnerEdit, SpaceOwnerGetOrCreate

from .guard import SandboxTransport, SandboxViolation, describe

ROOT = Path(__file__).parents[2]


async def main(execute: bool) -> int:
    tag = f"[TEST tehzor-python {time.strftime('%Y-%m-%d')} {secrets.token_hex(3)}]"
    name = f"{tag} Тестовый собственник"
    journal = ROOT / "reports" / f"sandbox-level1-{time.strftime('%Y%m%d-%H%M%S')}.jsonl"
    t = SandboxTransport(journal)
    async with TehzorClient(transport=t) as thz:
        so = thz.space_owners
        create = SpaceOwnerCreate(name=name, comment=f"{tag} создан автотестом, будет удалён")
        if not execute:
            print("DRY RUN — ничего не отправляется\n")
            print("1. create:\n   ", describe(await so.create(create, dry_run=True)))
            print(
                "2. edit:\n   ",
                describe(await so.edit("<id из шага 1>", SpaceOwnerEdit(comment=f"{tag} изменён"), dry_run=True)),
            )
            print(
                "3. get_or_create (тот же name — ожидается тот же id):\n   ",
                describe(await so.get_or_create(SpaceOwnerGetOrCreate(name=name), dry_run=True)),
            )
            print("4. delete:\n   ", describe(await so.delete("<id из шага 1>", dry_run=True)))
            # проверка защиты: чужой id блокируется до сети
            try:
                await so.edit("000000000000000000000000", SpaceOwnerEdit(comment="x"))
            except SandboxViolation as exc:
                print("\nЗащита песочницы:", exc)
            return 0

        print(f"Журнал: {journal.relative_to(ROOT)}\nМетка: {tag}\n")
        owner_ids: list[str] = []
        try:
            created = await so.create(create)
            oid = created.id
            print(f"1. create: id={oid!r}, name совпадает: {created.name == name}")
            if not oid:
                # spec: ответ на создание может не содержать id — берём его через get_or_create по тому же имени
                found = await so.get_or_create(SpaceOwnerGetOrCreate(name=name))
                oid = found.id
                print(f"   id из get_or_create: {oid!r}")
            if not oid:
                print("СТОП: не удалось получить id созданного собственника — удалите вручную по метке", tag)
                return 2
            t.track(oid, "space_owner")
            owner_ids.append(oid)

            edited = await so.edit(oid, SpaceOwnerEdit(comment=f"{tag} изменён"))
            print(
                f"2. edit: id={edited.id!r}, comment изменён: {bool(edited.comment and 'изменён' in edited.comment)}, "
                f"поля ответа: {sorted(k for k, v in edited.model_dump(exclude_none=True).items())}"
            )

            again = await so.get_or_create(SpaceOwnerGetOrCreate(name=name))
            same = again.id == oid
            print(f"3. get_or_create: id={again.id!r}, тот же собственник: {same}")
            if again.id and not same:
                t.track(again.id, "space_owner (get_or_create создал второго)")
                owner_ids.append(again.id)
        finally:
            for oid in owner_ids:
                try:
                    res = await so.delete(oid)
                    t.untrack(oid)
                    print(
                        f"4. delete {oid}: ответ {type(res).__name__}"
                        + (f" {sorted(res)}" if isinstance(res, dict) else f" {res!r}"[:60])
                    )
                except Exception as exc:
                    print(f"4. delete {oid}: ОШИБКА {type(exc).__name__}: {exc}. Удалите вручную по метке {tag}")
            if t.created:
                print("ОСТАЛИСЬ неудалённые:", sorted(t.created))
    return 0 if not t.created else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    sys.exit(asyncio.run(main(parser.parse_args().execute)))
