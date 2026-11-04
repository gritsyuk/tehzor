"""Выгрузка помещений объекта в Excel (по умолчанию — только квартиры).

    TEHZOR_API_KEY=… python examples/spaces_to_excel.py <id объекта> --type apartments --out spaces.xlsx

Список колонок пригоден для заполнения и обратной загрузки в update_spaces_from_excel.py.
"""

from __future__ import annotations

import argparse
import asyncio

from openpyxl import Workbook

from tehzor import TehzorClient
from tehzor.models.spaces import SpaceFilters


async def main(object_id: str, space_type: str | None, out: str, details: bool) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Помещения"
    ws.append(["space_id", "Номер", "Тип", "Этаж", "Статус", "plannedArea", "actualArea", "areaBTI",
               "typeDecoration"])
    async with TehzorClient() as thz:
        count = 0
        async for s in thz.spaces.iter(SpaceFilters(objects=[object_id])):
            if space_type and (not s.type or s.type.id != space_type):
                continue
            if details:  # список отдаёт сокращённую карточку; площади и отделка — в полной
                s = await thz.spaces.get(s.id)
            decoration = s.type_decoration.id if hasattr(s.type_decoration, "id") else s.type_decoration
            ws.append([s.id, s.name, s.type.name if s.type else None, s.floor,
                       s.status.name if s.status else None, s.planned_area, s.actual_area, s.area_bti, decoration])
            count += 1
    wb.save(out)
    print(f"{count} помещений → {out}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("object_id")
    parser.add_argument("--type", default="apartments", help="id типа помещения (spaces.types()); '' — все")
    parser.add_argument("--details", action="store_true", help="дочитать площади и отделку (запрос на помещение)")
    parser.add_argument("--out", default="spaces.xlsx")
    a = parser.parse_args()
    asyncio.run(main(a.object_id, a.type or None, a.out, a.details))
