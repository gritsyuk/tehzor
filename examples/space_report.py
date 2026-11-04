"""Отчёт по помещению: статус, приборы учёта, передачи собственникам, гарантийные обращения и их нарушения.

    TEHZOR_API_KEY=… python examples/space_report.py <id помещения>
"""

from __future__ import annotations

import argparse
import asyncio

from tehzor import TehzorClient


async def main(space_id: str) -> None:
    async with TehzorClient() as thz:
        space, status, meters, acceptances, claims = await asyncio.gather(
            thz.spaces.get(space_id), thz.spaces.get_status(space_id), thz.spaces.meters(space_id),
            thz.spaces.owner_acceptances(space_id), thz.spaces.warranty_claims(space_id),
        )
        print(f"Помещение {space.name} ({space.type.name if space.type else '—'}), этаж {space.floor}")
        print(f"Статус: {status.name}")
        print(f"Приборы учёта: {len(meters)}")
        for m in meters:
            last = max(m.consumptions or [], key=lambda c: c.created_at or 0, default=None)  # type: ignore[arg-type, return-value]
            print(f"  {m.type.name if m.type else '—'} №{m.serial_number}: последнее показание "
                  f"{last.value if last else '—'}")
        print(f"Передачи собственникам: {len(acceptances)}")
        for a in acceptances:
            print(f"  №{a.number}: {a.resolution.name if a.resolution else '—'}")
        print(f"Гарантийные обращения: {len(claims)}")
        for c in claims:
            problems = await thz.warranty_claims.problems(c.id)
            print(f"  №{c.number}: {c.status.name if c.status else '—'}, нарушений {len(problems)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("space_id")
    asyncio.run(main(parser.parse_args().space_id))
