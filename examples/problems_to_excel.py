"""Выгрузка нарушений объекта(ов) в Excel.

    pip install tehzor openpyxl
    TEHZOR_API_KEY=… python examples/problems_to_excel.py <id объекта> [<id объекта> …] --out problems.xlsx
"""

from __future__ import annotations

import argparse
import asyncio

from openpyxl import Workbook

from tehzor import TehzorClient
from tehzor.models.problems import ProblemFilters

WEB = "https://app.tehzor.ru"


async def main(objects: list[str], out: str, max_items: int | None) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Нарушения"
    ws.append(["Ссылка", "Объект", "Номер", "Стадия", "Статус", "Вид работ", "Помещение", "Этаж",
               "Срок устранения", "Создано", "Автор", "Описание"])
    async with TehzorClient() as thz:
        stages = {s.id: s.name for s in await thz.objects.stages()}
        count = 0
        async for p in thz.problems.iter(ProblemFilters(objects=objects), max_items=max_items):
            obj_id = p.object.id if p.object else ""
            ws.append([
                f'=HYPERLINK("{WEB}/objects/{obj_id}/problems/{p.id}", "Открыть")',
                p.object.name if p.object else None,
                p.number,
                stages.get(p.stage or "", p.stage),
                p.status.name if p.status else None,
                p.category.name if p.category else None,
                p.space.name if p.space else None,
                p.floor,
                p.planned_fix_date.replace(tzinfo=None) if p.planned_fix_date else None,
                p.created_at.replace(tzinfo=None) if p.created_at else None,
                p.created_by.full_name if p.created_by else None,
                p.description,
            ])
            count += 1
    wb.save(out)
    print(f"{count} нарушений → {out}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("objects", nargs="+", help="id объектов (UUID)")
    parser.add_argument("--out", default="problems.xlsx")
    parser.add_argument("--max", type=int, default=None, help="не больше N нарушений")
    a = parser.parse_args()
    asyncio.run(main(a.objects, a.out, a.max))
