"""Выгрузка приёмок работ объекта в Excel.

    TEHZOR_API_KEY=… python examples/work_acceptances_to_excel.py <id объекта> --out work_acceptances.xlsx
"""

from __future__ import annotations

import argparse
import asyncio

from openpyxl import Workbook

from tehzor import TehzorClient


def naive(dt):  # type: ignore[no-untyped-def]
    return dt.replace(tzinfo=None) if dt else None


async def main(object_id: str, out: str) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Приёмки работ"
    ws.append(["Номер", "Статус", "Вид работ", "Тип", "Фронт", "Начало", "Окончание", "Факт. приёмка",
               "Процент", "Объём", "Ед.", "Помещений", "Структур", "Описание"])
    async with TehzorClient() as thz:
        types = {t.id: t.name for t in await thz.work_acceptances.types()}
        fronts = {t.id: t.name for t in await thz.work_acceptances.front_types()}
        count = 0
        async for w in thz.work_acceptances.iter(object_id):
            scope = w.physical_work_scope
            ws.append([w.number, w.status.name if w.status else None, w.category.name if w.category else None,
                       types.get(w.type or "", w.type), fronts.get(w.front_type or "", w.front_type),
                       naive(w.acceptance_interval_start), naive(w.acceptance_interval_end),
                       naive(w.actual_acceptance_date), w.percent, scope.value if scope else None,
                       scope.unit_name if scope else None, len(w.space_ids or []), len(w.structure_ids or []),
                       w.description])
            count += 1
    wb.save(out)
    print(f"{count} приёмок → {out}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("object_id")
    parser.add_argument("--out", default="work_acceptances.xlsx")
    a = parser.parse_args()
    asyncio.run(main(a.object_id, a.out))
