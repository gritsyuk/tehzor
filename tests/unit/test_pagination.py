from __future__ import annotations

import pytest

from tehzor._pagination import iter_pages
from tehzor.errors import QueryTooHeavyError


def make_fetch(total: int, heavy_above: int | None = None, log: list[tuple[int, int]] | None = None):  # type: ignore[no-untyped-def]
    async def fetch(limit: int, offset: int) -> list[int]:
        if log is not None:
            log.append((limit, offset))
        if heavy_above is not None and limit > heavy_above:
            raise QueryTooHeavyError(502, "heavy")
        return list(range(offset, min(total, offset + limit)))

    return fetch


async def test_iterates_all_pages() -> None:
    log: list[tuple[int, int]] = []
    items = [x async for x in iter_pages(make_fetch(7, log=log), page_size=3)]
    assert items == list(range(7))
    assert log == [(3, 0), (3, 3), (3, 6)]


async def test_exact_multiple_needs_one_empty_page() -> None:
    log: list[tuple[int, int]] = []
    assert [x async for x in iter_pages(make_fetch(6, log=log), page_size=3)] == list(range(6))
    assert log[-1] == (3, 6)


async def test_max_items() -> None:
    log: list[tuple[int, int]] = []
    assert [x async for x in iter_pages(make_fetch(100, log=log), page_size=10, max_items=15)] == list(range(15))
    assert log == [(10, 0), (5, 10)]


async def test_halves_page_once_on_heavy_query() -> None:
    log: list[tuple[int, int]] = []
    items = [x async for x in iter_pages(make_fetch(60, heavy_above=25, log=log), page_size=50)]
    assert items == list(range(60))
    assert log[:2] == [(50, 0), (25, 0)]


async def test_heavy_after_halving_raises() -> None:
    with pytest.raises(QueryTooHeavyError):
        _ = [x async for x in iter_pages(make_fetch(60, heavy_above=10), page_size=50)]


async def test_invalid_page_size() -> None:
    with pytest.raises(ValueError):
        _ = [x async for x in iter_pages(make_fetch(1), page_size=0)]
