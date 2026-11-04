"""Обновление площадей и типа отделки помещений из Excel.

Колонки (первая строка — заголовки, как в spaces_to_excel.py): space_id, plannedArea, actualArea, areaBTI,
typeDecoration. Пустая ячейка — поле не меняется.

ПО УМОЛЧАНИЮ НИЧЕГО НЕ ОТПРАВЛЯЕТ — показывает запросы (dry_run). Отправка — только с --execute.

    TEHZOR_API_KEY=… python examples/update_spaces_from_excel.py spaces.xlsx            # посмотреть
    TEHZOR_API_KEY=… python examples/update_spaces_from_excel.py spaces.xlsx --execute  # отправить
"""

from __future__ import annotations

import argparse
import asyncio
import json

from openpyxl import load_workbook

from tehzor import TehzorClient, TehzorError
from tehzor.models.spaces import SpaceEdit

COLUMNS = {"plannedArea": "planned_area", "actualArea": "actual_area", "areaBTI": "area_bti",
           "typeDecoration": "type_decoration"}


def rows(path: str) -> list[tuple[str, SpaceEdit]]:
    ws = load_workbook(path, read_only=True).active
    it = ws.iter_rows(values_only=True)
    header = [str(h) if h is not None else "" for h in next(it)]
    result = []
    for values in it:
        row = dict(zip(header, values, strict=False))
        space_id = row.get("space_id")
        fields = {COLUMNS[k]: row[k] for k in COLUMNS if row.get(k) not in (None, "")}
        if space_id and fields:
            result.append((str(space_id), SpaceEdit(**fields)))
    return result


async def main(path: str, execute: bool) -> None:
    changes = rows(path)
    print(f"Изменений: {len(changes)} ({'ОТПРАВКА' if execute else 'dry run — ничего не отправляется'})")
    async with TehzorClient(max_concurrency=2) as thz:
        for space_id, edit in changes:
            if not execute:
                req = await thz.spaces.edit(space_id, edit, dry_run=True)
                print(" ", req.describe(), json.dumps(req.json, ensure_ascii=False))
                continue
            try:
                space = await thz.spaces.edit(space_id, edit)
                print(f"  {space.name}: ok")
            except TehzorError as exc:  # одна ошибка не останавливает остальные
                print(f"  {space_id}: ОШИБКА {exc}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("xlsx")
    parser.add_argument("--execute", action="store_true", help="действительно отправить изменения")
    a = parser.parse_args()
    asyncio.run(main(a.xlsx, a.execute))
